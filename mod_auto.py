from support_site import SupportCppl

from .mod_basic import ModelCoupangPlay
from .setup import *


class ModuleAuto(PluginModuleBase):
    def __init__(self, P):
        super(ModuleAuto, self).__init__(P, name='auto', first_menu='setting')
        self.db_default = {
            f"{self.name}_auto_start": "False",
            f"{self.name}_interval": "0 5 * * *",
            f"{self.name}_code_list": "",
        }

    def process_menu(self, page_name, req):
        arg = P.ModelSetting.to_dict()
        arg['is_include'] = scheduler.is_include(self.get_scheduler_id())
        arg['is_running'] = scheduler.is_running(self.get_scheduler_id())
        return render_template(f'{P.package_name}_{self.name}_{page_name}.html', arg=arg)

    def scheduler_function(self):
        
        program_list = P.ModelSetting.get_list(f"{self.name}_code_list")
        for code in program_list:
            data = {}
            data['program_info'] = SupportCppl.info(code)
            episodes = SupportCppl.episodes(code, data['program_info']['data']['seasons'], 1)

            if episodes['pagination']['page'] != episodes['pagination']['totalPages']:
                episodes = SupportCppl.episodes(code, data['program_info']['data']['seasons'], episodes['pagination']['totalPages'])
            db_item = ModelCoupangPlay.get(episodes['data'][-1]['id'])
            if db_item != None:
                continue
            data['info'] = SupportCppl.info(episodes['data'][-1]['id'])
            data['play_info'] = SupportCppl.play_info(data['info'])
            db_item = ModelCoupangPlay(data)
            db_item.save()
            db_item.init_for_queue()
            self.get_module('basic').download_queue.put(db_item)
            


