from support_site import SupportCppl

from .mod_basic import ModelCoupangPlay
from .setup import *


class ModuleSelect(PluginModuleBase):

    def __init__(self, P):
        super(ModuleSelect, self).__init__(P, name='select', first_menu='analysis')
        self.db_default = {
            f"{self.name}_recent_code": "",
        }
        self.last_data = None

    def process_menu(self, page_name, req):
        arg = P.ModelSetting.to_dict()
        if page_name == 'analysis':
            arg["code"] = request.args.get('code')
            if arg['code'] is None:
                arg['code'] = P.ModelSetting.get(f"{self.name}_recent_code")
        return render_template(f'{P.package_name}_{self.name}_{page_name}.html', arg=arg)
     

    def process_command(self, command, arg1, arg2, arg3, req):
        ret = {'ret':'success'}
        if command == 'analyze':
            ret = self.analyze(arg1)
        elif command == 'download':
            code = arg1
            db_item = ModelCoupangPlay.get(code)
            if db_item != None and arg2 != 'true':
                ret['ret'] = 'warning'
                ret['msg'] = '이미 DB에 있는 항목입니다.'
            elif arg2 == 'true' and db_item != None and ModelCoupangPlay.get_by_id_in_queue(db_item.id) != None:
                ret['ret'] = 'warning'
                ret['msg'] = '이미 큐에 있는 항목입니다.'
            else:
                if arg1 == self.last_data['code']: #영화
                    data = {'info':self.last_data['info'], 'play_info':self.last_data['play_info']}
                else:
                    data = {}
                    data['info'] = SupportCppl.info(code)
                    data['play_info'] = SupportCppl.play_info(data['info'])
                    data['program_info'] = self.last_data['info']
                db_item = ModelCoupangPlay(data)
                db_item.save()
                db_item.init_for_queue()
                self.get_module('basic').download_queue.put(db_item)
                ret['msg'] = "다운로드 큐에 넣었습니다."
        elif command == 'program_page':
            ret = self.analyze(arg1, arg2, arg3)
        elif command == 'download_program_check':
            lists = arg1[:-1].split(',')
            count = 0
            for code in lists:
                db_item = ModelCoupangPlay.get(code)
                # DB에 있고 큐에도 있다면 무신
                if db_item != None:# and ModelCoupangPlay.get_by_id_in_queue(db_item.id) != None:
                    continue
                data = {}
                data['info'] = SupportCppl.info(code)
                data['play_info'] = SupportCppl.play_info(data['info'])
                data['program_info'] = self.last_data['info']
                db_item = ModelCoupangPlay(data)
                db_item.save()
                db_item.init_for_queue()
                self.get_module('basic').download_queue.put(db_item)
            ret['msg'] = f"{len(lists)}개를 추가 하였습니다."     
        return jsonify(ret)


    def analyze(self, url, season=1, page=1):
        try:
            code = None
            if url.startswith('http'):
                match = re.search("titles/(?P<code>.*?)($|\/|\?)", url)
                if match:
                    code = match.group("code")
                else:
                    return {'ret':'warning', 'msg':'URL 분석 실패'}
            else:
                code = url
            info = SupportCppl.info(code)
            if info == None:
                return {'ret':'warning', 'msg':code + ' 잘못된 코드'}
            content_type = info['data']['as']
            P.ModelSetting.set(f"{self.name}_recent_code", code)
            P.logger.debug('Analyze %s %s', content_type, code)
             
            if content_type == 'TVSHOW':
                episodes = SupportCppl.episodes(code, season, page)
                P.ModelSetting.set(f"{self.name}_recent_code", code)
                self.last_data = {'content_type': content_type, 'code':code, 'info':info, 'episodes':episodes, 'season':season, 'page':page}
                return self.last_data
            elif content_type == 'MOVIE':
                play_info = SupportCppl.play_info(info)
                self.last_data = {'content_type': content_type, 'code':code, 'info' : info, 'play_info':play_info}
                return self.last_data
        except Exception as e: 
            P.logger.error(f'Exception:{str(e)}')
            P.logger.error(traceback.format_exc())    

    def plugin_load(self):
        from sjva import Auth
        if Auth.get_auth_status()['ret'] == False:
            raise Exception('auth fail!')

