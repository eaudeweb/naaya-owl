import sys
import logging
from optparse import OptionParser
from ConfigParser import SafeConfigParser
from subprocess import Popen, PIPE, STDOUT
import re
import os
from os import path
from datetime import date, datetime

usage = "usage: %prog [OPTIONS] <config_file>"
parser = OptionParser(usage=usage)
parser.add_option("-v", "--verbose",
                  action="store_const", const=logging.DEBUG, dest="loglevel")
parser.add_option("-q", "--quiet",
                  action="store_const", const=logging.CRITICAL, dest="loglevel")
parser.set_defaults(loglevel=logging.INFO)

log = logging.getLogger('nyowl')
log.setLevel(logging.DEBUG)

def lines(s):
    return s.strip().split('\n')

def parse_config(cfg_path):
    parser = SafeConfigParser()
    parser.read(cfg_path)

    def cfg_dict(section):
        return dict( (option, parser.get(section, option))
                     for option in parser.options(section) )

    config = cfg_dict('owl:main')
    buildouts = []
    for line in lines(config['buildouts']):
        name = line.strip()
        buildouts.append( (name, cfg_dict(name)) )

    config['buildouts'] = buildouts
    return config

def run_cmd(path, cmd):
    log.info('running command %r at %r', cmd, path)
    p = Popen(cmd, cwd=path, shell=True, stdout=PIPE, stderr=STDOUT)
    out = p.communicate()[0]
    log.debug('==========\n%s==========', out)
    log.info('done')
    return out

def main():
    options, args = parser.parse_args()

    if len(args) == 0:
        config_path = path.join(sys.prefix, 'owl.cfg')
    elif len(args) == 1:
        config_path = args[0]
    else:
        return parser.print_usage()

    handler = logging.StreamHandler()
    handler.setLevel(options.loglevel)
    log.addHandler(handler)

    config = dict(parse_config(config_path))
    config_folder = path.dirname(config_path)
    if config_folder:
        os.chdir(config_folder)

    report_name = date.today().strftime('%Y-%m-%d')
    report_path = path.join(config['output_root'], report_name)
    link_path = path.join(config['output_root'], 'current')

    report_path_0 = report_path
    n = 0
    while path.isdir(report_path):
        report_path = report_path_0 + '-' + str(n)
        n += 1
    os.mkdir(report_path)

    if path.islink(link_path):
        os.unlink(link_path)
    os.symlink(path.basename(report_path), link_path)

    report_file = file(path.join(report_path, 'report.txt'), 'wb')
    handler2 = logging.StreamHandler(report_file)
    handler2.setLevel(logging.INFO)
    log.addHandler(handler2)

    out = run_cmd('.', config['updatecmd'])
    with open(path.join(report_path, 'update.txt'), 'wb') as f:
        f.write(out)

    for name, options in config['buildouts']:
        log.info('running tests for %r', name)

        out = run_cmd(options['path'], options['testcmd'])
        with open(path.join(report_path, name+'_out.txt'), 'wb') as f:
            f.write(out)

        m = re.search(r'Total: (?P<tests>\d*) tests, '
                      r'(?P<failures>\d*) failures, '
                      r'(?P<errors>\d*) errors\s*$',
                      out)

        if m is None:
            m = re.search(r'Ran (?P<tests>\d*) tests with '
                          r'(?P<failures>\d*) failures and '
                          r'(?P<errors>\d*) errors in \d*\.?\d* seconds\.',
                          out)
            if m is None:
                log.error('unexpected output from test process')
                continue

        n_tests = int(m.group('tests'))
        n_failures = int(m.group('failures'))
        n_errors = int(m.group('errors'))

        if n_errors or n_failures:
            log.info('Tests failed: %d errors, %d failures',
                     n_errors, n_failures)
        else:
            log.info('Tests successful')

    handler2.close()
    report_file.close()

if __name__ == '__main__':
    main()
