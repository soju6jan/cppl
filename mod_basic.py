import wv_tool
from support_site import SupportCppl

from .setup import *


class ModuleBasic(PluginModuleBase):
    download_queue = None
    download_thread = None
    current_download_count = 0

    def __init__(self, P):
        super(ModuleBasic, self).__init__(P, name='basic', first_menu='list')
        self.db_default = {
            f"item_last_list_option": "",
            f"{self.name}_db_version": "1",
            f"{self.name}_save_path": "{PATH_DATA}" + os.sep +"download",
            f"{self.name}_make_title_folder": "false",
            f"{self.name}_max_download_count": "2",
            f"{self.name}_incompleted_redownload": "false",
            f"{self.name}_curl": "",
        }
        self.web_list_model = ModelCoupangPlay
        default_route_socketio_module(self, attach='/queue')


    def process_command(self, command, arg1, arg2, arg3, req):
        ret = {'ret':'success'}
        if command == 'analyze':
            ret = self.get_module('basic').analyze(arg1)
            P.ModelSetting.set(f"{self.name}_recent_code", arg1)
        elif command == 'queue_list':
            ret = [x.as_dict_for_queue() for x in ModelCoupangPlay.queue_list]
        elif command == 'program_list_command':
            if arg1 == 'remove_completed':
                count = ModelCoupangPlay.remove_all(True)
                ret['msg'] = f"{count}개를 삭제하였습니다."
            elif arg1 == 'remove_incomplete':
                items = ModelCoupangPlay.get_incompleted()
                for item in items:
                    wv_tool.WVDownloader.stop_by_callback_id(f"{P.package_name}_{self.name}_{item.id}")
                count = ModelCoupangPlay.remove_all(False)
                ret['msg'] = f"{count}개를 삭제하였습니다."
            elif arg1 == 'add_incomplete':
                count = self.incompleted_redownload()
                ret['msg'] = f"{count}개를 추가 하였습니다."
            elif arg1 == 'remove_one':
                result = ModelCoupangPlay.delete_by_id(arg2)
                if result:
                    ret['msg'] = '삭제하였습니다.'
                else:
                    ret['ret'] = 'warning'
                    ret['msg'] = '실패하였습니다.'
        elif command == 'queue_command':
            if arg1 == 'cancel':
                queue_item = ModelCoupangPlay.get_by_id_in_queue(arg2)
                queue_item.status = "CANCEL"
                queue_item.cancel = True
                queue_item.completed = True
                queue_item.completed_time = datetime.now()
                queue_item.save()
                wv_tool.WVDownloader.stop_by_callback_id(f"{P.package_name}_{arg2}")
                ret['msg'] = "취소하였습니다."
            elif arg1 == 'reset':
                if self.download_queue is not None:
                    with self.download_queue.mutex:
                        self.download_queue.queue.clear()
                for _ in wv_tool.WVDownloader.get_list():
                    if _.callback_id.startswith(f"{P.package_name}_"):
                        _.stop()
                ModelCoupangPlay.queue_list = []
            elif arg1 == 'delete_completed':
                new = []
                for _ in ModelCoupangPlay.queue_list:
                    if _.completed == False:
                        new.append(_)
                ModelCoupangPlay.queue_list = new
        return jsonify(ret)


    def plugin_load(self):
        SupportCppl.initialize(P.ModelSetting.get(f"{self.name}_curl"))
        if self.download_queue is None:
            self.download_queue = queue.Queue()
        if self.download_thread is None:
            self.download_thread = threading.Thread(target=self.download_thread_function, args=())
            self.download_thread.daemon = True  
            self.download_thread.start()
        if P.ModelSetting.get_bool(f"{self.name}_incompleted_redownload"):
            self.incompleted_redownload()
       

    def download_thread_function(self):
        while True:
            try:
                while True:
                    if self.current_download_count < P.ModelSetting.get_int(f"{self.name}_max_download_count"):
                        break
                    time.sleep(5)
                db_item = self.download_queue.get()
                if db_item.cancel:
                    self.download_queue.task_done() 
                    continue
                if db_item is None:
                    self.download_queue.task_done() 
                    continue
                wv = db_item.content_info['play_info']['wv']
                wv['callback_id'] = f"{P.package_name}_{db_item.id}"
                wv['clean'] = False
                wv['folder_tmp'] = os.path.join(F.config['path_data'], 'tmp')
                wv['folder_output'] = ToolUtil.make_path(P.ModelSetting.get(f"{self.name}_save_path"))
                wv['output_filename'] = SupportCppl.get_filename(db_item.content_info)
                downloader = wv_tool.WVDownloader(wv, callback_function=self.wvtool_callback_function)
                downloader.logger = P.logger
                downloader.start()
                self.current_download_count += 1
                self.download_queue.task_done() 
            except Exception as e: 
                logger.error(f"Exception:{str(e)}")
                logger.error(traceback.format_exc())


    def db_delete(self, day):
        return ModelCoupangPlay.delete_all(day=day)

    def incompleted_redownload(self):
        failed_list = ModelCoupangPlay.get_incompleted()
        for item in failed_list:
            item.init_for_queue()
            self.download_queue.put(item)
        return len(failed_list)


    def wvtool_callback_function(self, args):
        try:
            db_item = ModelCoupangPlay.get_by_id_in_queue(args['data']['callback_id'].split('_')[-1])
            if db_item is None:
                return
            is_last = True

            if args['status'] in ["READY", "SEGMENT_FAIL"]:
                is_last = False
            elif args['status'] in ["EXIST_OUTPUT_FILEPATH", 'USER_STOP', "COMPLETED"]:
                pass
            elif args['status'] == "DOWNLOADING":
                is_last = False
            
            db_item.status = args['status']
            if is_last:
                self.current_download_count += -1
                db_item.completed = True
                db_item.completed_time = datetime.now()
                db_item.save()
            self.socketio_callback('status', db_item.as_dict_for_queue())
        except Exception as e: 
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())





class ModelCoupangPlay(ModelBase):
    P = P
    __tablename__ = f'{P.package_name}_item'
    __table_args__ = {'mysql_collate': 'utf8_general_ci'}
    __bind_key__ = P.package_name

    id = db.Column(db.Integer, primary_key=True)
    created_time    = db.Column(db.DateTime)
    completed_time  = db.Column(db.DateTime)
    
    content_type = db.Column(db.String)
    content_info = db.Column(db.JSON)
    code = db.Column(db.String)
    title = db.Column(db.String)
    season_number  = db.Column(db.String)
    episode_number  = db.Column(db.String)
    completed       = db.Column(db.Boolean)
    cancel = db.Column(db.Boolean)
    poster = db.Column(db.String)
    queue_list = []

    def __init__(self, data):
        self.completed      = False 
        self.created_time = datetime.now()
        self.content_type = data['info']['data']['as']
        self.content_info = data
        self.code = data['info']['data']['id']
        self.cancel = False
        if self.content_type == 'MOVIE':
            self.title = data['info']['data']['title']
            self.poster = data['info']['data']['images']['poster']['url']
        elif self.content_type == 'EPISODE':
            self.title = data['program_info']['data']['title'] + ', ' + data['info']['data']['title']
            self.poster = data['info']['data']['images']['story-art']['url']


    def init_for_queue(self):
        self.status = 'READY'
        self.queue_list.append(self)


    @classmethod
    def get(cls, code):
        with F.app.app_context():
            return db.session.query(cls).filter_by(
                code=code,
            ).order_by(desc(cls.id)).first()


    @classmethod
    def is_duplicate(cls, code):
        return (cls.get(code) != None)


    # 오버라이딩
    @classmethod
    def make_query(cls, req, order='desc', search='', option1='all', option2='all'):
        with F.app.app_context():
            query = F.db.session.query(cls)
            query = cls.make_query_search(query, search, cls.title)
            if option1 == 'completed':
                query = query.filter_by(completed=True)
            elif option1 == 'incompleted':
                query = query.filter_by(completed=False)
            if order == 'desc':
                query = query.order_by(desc(cls.id))
            else:
                query = query.order_by(cls.id)
            return query 


    @classmethod
    def remove_all(cls, is_completed=True): # to remove_all(True/False)
        with F.app.app_context():
            count = db.session.query(cls).filter_by(completed=is_completed).delete()
            db.session.commit()
            return count

    @classmethod
    def get_incompleted(cls):
        with F.app.app_context():
            return db.session.query(cls).filter_by(
                completed=False
            ).all()
       

    ### only for queue
    @classmethod
    def get_by_id_in_queue(cls, id):
        for _ in cls.queue_list:
            if _.id == int(id):
                return _

    def as_dict_for_queue(self):
        ret = self.as_dict()
        ret['status'] = self.status
        return ret
