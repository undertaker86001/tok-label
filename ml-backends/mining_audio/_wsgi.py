"""
矿业声音ML Backend的WSGI应用入口

基于Label Studio ML Backend的标准模式实现
"""

import os
import json
import argparse
import logging
import logging.config

# 设置默认日志级别
log_level = os.getenv("LOG_LEVEL", "INFO")

logging.config.dictConfig({
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": "[%(asctime)s] [%(levelname)s] [%(name)s::%(funcName)s::%(lineno)d] %(message)s"
        }
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "level": log_level,
            "stream": "ext://sys.stdout",
            "formatter": "standard"
        }
    },
    "root": {
        "level": log_level,
        "handlers": ["console"],
        "propagate": True
    }
})

from label_studio_ml.api import init_app
from model import MiningAudioMLBackend

_DEFAULT_CONFIG_PATH = os.path.join(os.path.dirname(__file__), 'config.json')


def get_kwargs_from_config(config_path=_DEFAULT_CONFIG_PATH):
    """从配置文件获取初始化参数"""
    if not os.path.exists(config_path):
        return dict()
    with open(config_path) as f:
        config = json.load(f)
    assert isinstance(config, dict)
    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='矿业声音ML Backend')
    parser.add_argument(
        '-p', '--port', dest='port', type=int, default=9090,
        help='Server port')
    parser.add_argument(
        '--host', dest='host', type=str, default='0.0.0.0',
        help='Server host')
    parser.add_argument(
        '--kwargs', '--with', dest='kwargs', metavar='KEY=VAL', nargs='+', 
        type=lambda kv: kv.split('='),
        help='Additional MiningAudioMLBackend initialization kwargs')
    parser.add_argument(
        '-d', '--debug', dest='debug', action='store_true',
        help='Switch debug mode')
    parser.add_argument(
        '--log-level', dest='log_level', 
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'], default=log_level,
        help='Logging level')
    parser.add_argument(
        '--model-dir', dest='model_dir', default=os.path.dirname(__file__),
        help='Directory where models are stored')
    parser.add_argument(
        '--check', dest='check', action='store_true',
        help='Validate model instance before launching server')
    parser.add_argument('--basic-auth-user',
                         default=os.environ.get('ML_SERVER_BASIC_AUTH_USER', None),
                         help='Basic auth user')
    parser.add_argument('--basic-auth-pass',
                         default=os.environ.get('ML_SERVER_BASIC_AUTH_PASS', None),
                         help='Basic auth pass')
    
    args = parser.parse_args()

    if args.log_level:
        logging.root.setLevel(args.log_level)

    def isfloat(value):
        try:
            float(value)
            return True
        except ValueError:
            return False

    def parse_kwargs():
        param = dict()
        if args.kwargs:
            for k, v in args.kwargs:
                if v.isdigit():
                    param[k] = int(v)
                elif v == 'True' or v == 'true':
                    param[k] = True
                elif v == 'False' or v == 'false':
                    param[k] = False
                elif isfloat(v):
                    param[k] = float(v)
                else:
                    param[k] = v
        return param

    kwargs = get_kwargs_from_config()
    if args.kwargs:
        kwargs.update(parse_kwargs())

    if args.check:
        print('Check "' + MiningAudioMLBackend.__name__ + '" instance creation..')
        model = MiningAudioMLBackend(**kwargs)

    app = init_app(
        model_class=MiningAudioMLBackend, 
        basic_auth_user=args.basic_auth_user, 
        basic_auth_pass=args.basic_auth_pass
    )
    app.run(host=args.host, port=args.port, debug=args.debug)

else:
    # 用于uWSGI
    app = init_app(model_class=MiningAudioMLBackend)
