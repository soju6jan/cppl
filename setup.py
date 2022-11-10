DEFINE_DEV = False

setting = {
    'filepath' : __file__,
    'use_db': True,
    'use_default_setting': True,
    'home_module': None,
    'menu': {
        'uri': __package__,
        'name': '쿠팡플레이',
        'list': [
            {
                'uri': 'basic/setting',
                'name': '설정',
            },
            {
                'uri': 'basic/list',
                'name': '목록',
            },
            {
                'uri': 'basic/queue',
                'name': '다운로드 큐',
            },
            {
                'uri': 'select',
                'name': '선택',
                'list': [
                    {'uri': 'analysis', 'name': '분석'},
                ]
            },
            {
                'uri': 'auto/setting',
                'name': '자동',
            },
            {
                'uri': 'manual',
                'name': '매뉴얼',
                'list': [
                    {'uri': 'files/manual.md' if DEFINE_DEV else "files/manual.mdf", 'name': '기본'},
                ]
            },
            {
                'uri': 'log',
                'name': '로그',
            },
        ]
    },
    'default_route': 'normal',
}
from plugin import *

P = create_plugin_instance(setting)
try:
    from .mod_auto import ModuleAuto
    from .mod_basic import ModuleBasic
    from .mod_select import ModuleSelect
    P.set_module_list([ModuleBasic, ModuleSelect, ModuleAuto])
except Exception as e:
    P.logger.error(f'Exception:{str(e)}')
    P.logger.error(traceback.format_exc())
