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
parser.add_option("-n", "--no-mail",
                  action="store_false", dest="send_mail", default=True)
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
    cmd_options, args = parser.parse_args()

    if len(args) == 0:
        config_path = path.join(sys.prefix, 'owl.cfg')
    elif len(args) == 1:
        config_path = args[0]
    else:
        return parser.print_usage()

    handler = logging.StreamHandler()
    handler.setLevel(cmd_options.loglevel)
    log.addHandler(handler)

    config = dict(parse_config(config_path))
    config_folder = path.dirname(config_path)
    if config_folder:
        os.chdir(config_folder)

    report_name = date.today().strftime('%Y-%m-%d')
    report_path = path.join(config['output_root'], report_name)
    link_path = path.join(config['output_root'], 'current')

    report_path_0 = report_path
    n = 1
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
    handler2.setFormatter(logging.Formatter('[%(asctime)s] %(message)s'))
    log.addHandler(handler2)

    def send_fail_mail(name, output):
        if not cmd_options.send_mail:
            return
        recipients = map(str.strip, config['error_emails'].strip().split('\n'))
        subject = 'owl failure in %r' % name

        mail = mail_sender('mail.eaudeweb.ro', 25)
        try:
            mail('Night Owl <alex.morega@eaudeweb.ro>',
                 recipients, subject, output, include_owl=True)
        except mail.RecipientsRefused, e:
            log.error('SMTP recipients refused: %r', e.recipients)
        except Exception, e:
            log.error('SMTP error: %r', e)

    out = run_cmd('.', config['updatecmd'])
    with open(path.join(report_path, 'update.txt'), 'wb') as f:
        f.write(out)

    for name, options in config['buildouts']:
        if 'pre_test' in options:
            log.info('updating %r', name)
            pre_test_out = run_cmd(options['path'], options['pre_test'])
            p = path.join(report_path, name+'_pre_test_out.txt')
            with open(p, 'wb') as f:
                f.write(p)

        log.info('running tests for %r', name)

        out = run_cmd(options['path'], options['testcmd'])
        with open(path.join(report_path, name+'_out.txt'), 'wb') as f:
            f.write(out)

        m = re.search(r'Ran (?P<tests>\d+) tests in [\d\.]+s\s+'
                      r'(?P<result>OK|FAILED)', out)

        if m is None:
            log.error('unexpected output from test process')
            send_fail_mail(name, out)
            continue

        n_tests = int(m.group('tests'))
        success = {'OK': True, 'FAILED': False}.get(m.group('result'))

        if success:
            log.info('Tests successful')
        else:
            log.info('Tests failed')
            send_fail_mail(name, out)

    handler2.close()
    report_file.close()

def mail_sender(host, port):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.image import MIMEImage

    class RecipientsRefused(ValueError):
        def __init__(self, recipients):
            self.recipients = recipients

    def send_mail(addr_from, addr_to_list, subject, body, include_owl=False):
        msg = MIMEMultipart()
        msg['From'] = addr_from
        for addr_to in addr_to_list:
            msg['To'] = addr_to
        msg['Subject'] = subject

        if include_owl:
            owl_file_path = path.join(path.dirname(__file__), 'owl.jpg')
            with open(owl_file_path, 'rb') as owl_file:
                msg.attach(MIMEImage(owl_file.read()))
            body = '\n\n' + body

        msg.attach(MIMEText(body))

        s = smtplib.SMTP(host, port)
        try:
            ret = s.sendmail(addr_from, addr_to_list, msg.as_string())
        except smtplib.SMTPRecipientsRefused, e:
            ret = e.recipients
        finally:
            s.quit()
        if ret:
            raise RecipientsRefused(ret)

    send_mail.RecipientsRefused = RecipientsRefused
    return send_mail

def test_mail(addr_to):
    send_mail = mail_sender('mail.eaudeweb.ro', 25)
    send_mail('Night Owl <alex.morega@eaudeweb.ro>', [addr_to],
              'hello world', 'the error text', include_owl=True)

if __name__ == '__main__':
    main()
