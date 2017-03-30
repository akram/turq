import argparse
import logging
import sys
import threading

import coloredlogs

import turq.editor
import turq.mock
from turq.util.http import guess_external_url

DEFAULT_ADDRESS = ''       # All interfaces
DEFAULT_MOCK_PORT = 13085
DEFAULT_EDITOR_PORT = 13086
DEFAULT_RULES = 'error(404)\n'


def main():
    args = parse_args(sys.argv)
    if not args.verbose:
        sys.excepthook = excepthook
    setup_logging(args)
    run(args)


def parse_args(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='print more verbose diagnostics')
    parser.add_argument('--no-color', action='store_true',
                        help='do not colorize console output')
    parser.add_argument('--no-editor', action='store_true',
                        help='disable the built-in Web-based rules editor')
    parser.add_argument('-b', '--bind', metavar='ADDRESS',
                        default=DEFAULT_ADDRESS,
                        help='IP address or hostname to listen on')
    parser.add_argument('-p', '--mock-port', metavar='PORT', type=int,
                        default=DEFAULT_MOCK_PORT,
                        help='port for the mock server to listen on')
    parser.add_argument('--editor-port', metavar='PORT', type=int,
                        default=DEFAULT_EDITOR_PORT,
                        help='port for the rules editor to listen on')
    parser.add_argument('-6', '--ipv6', action='store_true',
                        default=False,
                        help='listen on IPv6 instead of IPv4')
    parser.add_argument('-r', '--rules', metavar='PATH',
                        type=argparse.FileType('r'),
                        help='file with initial rules code')
    return parser.parse_args(argv[1:])


def excepthook(_type, exc, _traceback):
    sys.stderr.write('turq: error: %s\n' % exc)


def setup_logging(args):
    fmt = '%(asctime)-10s %(name)-21s %(message)s'
    datefmt = '%H:%M:%S'
    if args.no_color:
        formatter = logging.Formatter(fmt, datefmt)
    else:
        formatter = coloredlogs.ColoredFormatter(
            fmt, datefmt,
            # I don't like how it paints the time green by default.
            field_styles=dict(coloredlogs.DEFAULT_FIELD_STYLES, asctime={}))
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)
    turq_root = logging.getLogger('turq')
    turq_root.addHandler(handler)
    turq_root.setLevel(logging.DEBUG if args.verbose else logging.INFO)


def run(args):
    rules = args.rules.read() if args.rules else DEFAULT_RULES
    mock_server = turq.mock.MockServer(args.bind, args.mock_port, args.ipv6,
                                       rules)

    if args.no_editor:
        editor_server = None
    else:
        editor_server = turq.editor.make_server(args.bind, args.editor_port,
                                                args.ipv6, mock_server)
        threading.Thread(target=editor_server.serve_forever).start()

    # Show mock server info just before going into `serve_forever`,
    # to minimize the delay between printing it and actually listening
    show_server_info('mock', mock_server)
    if editor_server is not None:
        show_server_info('editor', editor_server)

    try:
        mock_server.serve_forever()
    except KeyboardInterrupt:
        mock_server.server_close()
        sys.stderr.write('\n')

    if editor_server is not None:
        editor_server.shutdown()
        editor_server.server_close()


def show_server_info(label, server):
    (host, port, *_) = server.server_address
    logging.getLogger('turq').info('%s on %s port %d - try %s',
                                   label, host, port,
                                   guess_external_url(host, port))


if __name__ == '__main__':
    main()
