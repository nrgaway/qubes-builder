#! /usr/bin/env python
# -*- coding: utf-8 -*-

# setup.py --- Qubes Builder Configuration Utiltiy
#
# Copyright (C) 2015  Jason Mehring
#
# License: GPL-2+
# ------------------------------------------------------------------------------
# Install 'dialog' program if it does not yet exist
# ------------------------------------------------------------------------------

'''
TODO:
  - overrides or merge .setup.data
  - BUILDER_PLUGINS selection
  - combine release.conf and setup.conf into builder.conf
'''

from __future__ import unicode_literals
import sys
import os
import locale
import codecs
import argparse
import collections
import shutil
import re
import types

import sh

from ConfigParser import ConfigParser
from textwrap import dedent
from ansi import ANSIColor

locale.setlocale(locale.LC_ALL, '')
DIALOG = 'dialog'

try:
    from textwrap import indent
except ImportError:
    def indent(text, prefix, predicate=None):
        l = []

        for line in text.splitlines(True):
            if (callable(predicate) and predicate(line)) \
               or (not callable(predicate) and predicate) \
               or (predicate is None and line.strip()):
                line = prefix + line
            l.append(line)

        return ''.join(l)


def dialog_infobox(*varargs, **kwargs):
    '''Display text in infodialog.

    Only displays if text is provided. Text can be provided in varargs
    '''
    info = {
        'title':  'Qubes Setup Information.',
        'width': 60,
        'height': 8,
        'text': ''
    }

    info.update(kwargs)
    if varargs:
        info['text'] = ' '.join(varargs)

    if info['text']:
        dialog.infobox(**info)


def exit(*varargs, **kwargs):
    '''Function to exit.  Maybe restoring some files before exiting.
    '''
    kwargs['title'] = 'System Exit!'
    dialog_infobox(*varargs, **kwargs)

    # Restore original template.conf
    config = Config(None)
    if os.path.exists(config.conf_builder + '.bak'):
        shutil.move(config.conf_builder + '.bak', config.conf_builder)

    sys.exit()


def getchar():
    try:
        import termios
    except ImportError:
        import msvcrt
        return msvcrt.getchar()

    import sys, tty
    def _getchar():
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            char = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return char
    return _getchar()


#------------------------------------------------------------------------------
# Prompt to install required depend 'dialog' if it does not exist
#------------------------------------------------------------------------------
if not sh.which(DIALOG):
    import time
    from sh import sudo

    ansi = ANSIColor()
    os.system('clear')

    print '{ansi[red]}{0}{ansi[blue]} is not installed and required for setup.{ansi[normal]}\r\r'.format(DIALOG, ansi=ansi)
    print '\nEnter \'Y\' to install now or anything else to quit [YyNnQq]: '
    char =  getchar()
    if char.lower() != 'y':
        print '\nYou selected not to install {ansi[blue]}{0}{ansi[normal]} and therefore setup must now exit'.format(DIALOG, ansi=ansi)
        print 'Exiting!'
        exit()

    os.system('clear')
    runnning = sudo.yum('-y', 'install', 'dialog', _bg=True)
    sys.stdout.write('Waiting for {ansi[red]}{0}{ansi[normal]} to install'.format(DIALOG, ansi=ansi))
    sys.stdout.flush()
    while os.path.exists('/proc/{0}'.format(runnning.pid)):
        sys.stdout.write('{ansi[red]}.{ansi[normal]}'.format(ansi=ansi))
        sys.stdout.flush()
        time.sleep(1)
    print

# Initialize a dialog.Dialog instance
from dialog import Dialog
dialog = Dialog(dialog='dialog')
dialog.set_background_title("Qubes Builder Configuration Utility")


def write_file(filename, text):
    try:
        with codecs.open(filename, 'w', 'utf8') as outfile:
            outfile.write(dedent(text))
    except IOError, err:
        exit(err)


import shlex
def parse_brackets(text):
    '''A very simple lexer to parse round brackets.
    '''
    ansi = ANSIColor()

    lexer = shlex.shlex(text)
    lexer.whitespace = '\t\r\n'

    text = ''
    raw = ''
    count =  0

    for token in lexer:
        chars = token
        if  chars[0] in '\'"' and chars[-1] in '\'"':
            new_chars = parse_brackets(chars[1:-1])
            text += chars[0] + new_chars + chars[-1]
            continue
        if token == '(':
            count += 1
            if raw and raw[-1] == '$':
                chars = '{ansi[blue]}{0}'.format(chars, ansi=ansi)
        elif token == ')':
            if count == 1:
                chars = '{0}{ansi[normal]}'.format(chars, ansi=ansi)
            count -= 1
        elif count:
            if raw and raw[-1] != '(':
                chars = '{ansi[black]}{0}'.format(chars, ansi=ansi)

        raw += token
        text += chars

    return text

def display_configuration(filename):
    '''Display the configuration file.
    '''
    ansi = ANSIColor()
    os.system('clear')
    try:
        with codecs.open(filename, 'r', 'utf8') as infile:
            for line in infile:
                match = re.match(r'(?P<text>.*?(?=#)|.*)(?P<comment>([#]+.*)|)', line.rstrip())
                if match:
                    line = ''
                    text = match.groupdict()['text']
                    comment = match.groupdict()['comment']
                    if match.groupdict()['text']:
                        var = re.match(r'(?P<var>.*)(?P<text>[?:]?=.*)', text)
                        target = re.match(r'(?P<target>.*[:]+)(?P<text>.*)', text)
                        #text = re.sub(r'(\$[(].*[)])', r'{ansi[blue]}\1{ansi[normal]}'.format(ansi=ansi), text)
                        text = parse_brackets(text)

                        if var:
                            line += '{ansi[blue]}{d[var]}{ansi[normal]}{d[text]}'.format(d=var.groupdict(), ansi=ansi)
                        elif target:
                            line += '{ansi[red]}{d[target]}{ansi[normal]}{d[text]}'.format(d=target.groupdict(), ansi=ansi)
                        else:
                            line += '{ansi[black]}{0}{ansi[normal]}'.format(text, ansi=ansi)

                    if comment:
                        line += '{ansi[green]}{0}{ansi[normal]}'.format(comment, ansi=ansi)
                print line
    except IOError, err:
        exit(err)


def soft_link(source, target):
    '''Attempt to soft-link a file.  Exit with message on failure.
    '''
    try:
        if os.path.exists(target) and not os.path.islink(target):
            message = 'Setup will not over-write regular files that are not soft-linked.'
            exit('Error linking:\n{0} to {1}\n\n{2}'.format(source, target, message))

        if os.path.exists(source):
            if os.path.exists(target):
                os.remove(target)
            os.symlink(source, target)
        else:
            message = 'Target file does not exist and therefore cannot be linked.'
            exit('Error linking:\n{0} to {1}\n\n{2}'.format(source, target, message))
    except OSError, e:
        exit('Error linking:\n{0} to {1}\n\n{2}.'.format(source, target, e.strerror))


def dialog_release(release):
    '''Select release version of Qubes to build.
    '''
    release = str(release)
    default_button = 'yes' if release == '2' else 'no'

    code = dialog.yesno(**{
        'title':  'Choose Qubes Version',
        'width': 60,
        'height': 8,
        'yes_label': 'Release 2',
        'no_label': 'Release 3',
        'default_button': default_button,
        'text': dedent('''\
            Choose which version of Qubes you wish to build.

            Valid options are either the stable release 2 or development release 3 version.
        '''),
    })

    if code == dialog.OK:
        return '2'
    elif code == dialog.CANCEL:
        return '3'
    elif code == dialog.ESC:
        exit('Escape key pressed. Exiting.')


# ------------------------------------------------------------------------------
# useOverrideConfiguration
# ------------------------------------------------------------------------------
def dialog_override(override_source):
    _info = {
        'title':  'Use Branch Specific Override Configuration File?',
        'width': 60,
        'height': 8,
        'default_button': 'yes',
        'text': dedent('''\
            A  branch specific configuration file was found in your personal directory:
            {0}.

            Would you like to use and override the other provided repos?
        '''.format(override_source)),
    }

    code = dialog.yesno(**_info)

    if code == dialog.OK:
        return True
    elif code == dialog.CANCEL:
        return False
    elif code == dialog.ESC:
        exit('User aborted setup.')


def dialog_repo(choices):
    '''Display 'choose repo' dialog.
    '''
    _info = {
        'title':  'Choose Repos To Use To Build Packages',
        'width': 76,
        'height': 16,
    }

    while True:
        code, tag = dialog.radiolist(
            "Choose Repos To Use To Build Packages", width=76,
            choices=choices, help_button=True, help_status=True)

        if code == 'help':
            tag, selected, choices = tag
            dialog.msgbox("You asked for help about something called '{0}'. "
                          "Sorry, but I am quite incompetent in this matter."
                          .format(tag))

        elif code == dialog.CANCEL:
            exit('User aborted setup.')

        elif code == dialog.ESC:
            exit('User aborted setup.')

        else:
            # 'tag' is the chosen tag
            break

    return tag


def dialog_ssh_access(default=False):
    ''''''
    default_button = 'yes' if default else 'no'

    code = dialog.yesno(**{
        'title':  'Enable SSH Access',
        'width': 60,
        'height': 8,
        'default_button': default_button,
        'text': dedent('''\
            Do you have ssh access to the repos?

            Select 'Yes' to configure urls to match git or 'No' for https"
        '''),
    })

    if code == dialog.OK:
        return True
    elif code == dialog.CANCEL:
        return False
    elif code == dialog.ESC:
        exit('Escape key pressed. Exiting.')


def dialog_template_only(default=False):
    '''Dialog to display choice of building only templates.
    '''
    default_button = 'yes' if default else 'no'

    code = dialog.yesno(**{
        'title':  'Build Template Only?',
        'width': 60,
        'height': 8,
        'default_button': default_button,
        'text': dedent('''\
            Would you like to build only the templates?

            Select 'Yes' to to only build templates or 'No' for complete build
        '''),
    })

    if code == dialog.OK:
        return True
    elif code == dialog.CANCEL:
        return False
    elif code == dialog.ESC:
        exit('Escape key pressed. Exiting.')


def dialog_dists(choices, helper):
    '''Display VM's for selction.
    '''

    info = {
        'height': 0,
        'width': 0,
        'list_height': 0,
        'choices': choices,
        'title': 'Template Distribution Selection',
        'help_button': True,
        'item_help': True,
        'help_tags': True,
        'help_status': True,
        'text': dedent('''\
            Left column contains DIST name
            Right column contains TEMPLATE_LABEL
        '''),
    }

    while True:
        code, tag = dialog.checklist(**info)
        if code == 'help':
            tag, selected_tags, choices = tag
            dialog.msgbox(helper.get(tag, 'No Help available for {0}'.format(tag)), height=7, width=60)
        else:
            break

    string = '\n'.join(tag)
    dialog.msgbox('The following distributions will be added to the builder configuration:\n\n'
                  '{0}'.format(indent(string, '  ')), height=15, width=60,
                  title='Selected Distributions',
                  no_collapse=True)

    return tag


def dialog_verify_keys(config, force=False):
    for key in config.keys:
        try:
            text = sh.gpg('--list-key', key)
        except sh.ErrorReturnCode, err:
            # exit_code will be non-zero and will trigger installation and verification of keys
            pass

        if force or text.exit_code:
            if force:
                message = u'{key[owner]} forced get.\n\nSelect "Yes" to re-add or "No" to exit'.format(key=config.keys[key])
            else:
                message = u'{key[owner]} key does not exist.\n\nSelect "Yes" to add or "No" to exit'.format(key=config.keys[key])

            code = dialog.yesno(**{
                'title':  'Add Keys',
                'width': 60,
                'height': 8,
                'default_button': 'yes',
                'text': message,
            })

            if code != dialog.OK:
                exit('User aborted setup: Exiting setup since keys can not be installed')

            # Receive key from keyserver
            else:
                try:
                    text = sh.gpg('--keyserver', 'pgp.mit.edu', '--recv-keys', key)
                except sh.ErrorReturnCode, err:
                    exit('Unable to receive keys from keyserver.  Try again later or install them manually')

        # Verify key on every run
        result = self.gpg_verify_key(key)
        if not result:
            info = {
                'title':  '{key[owner]} fingerprint failed!'.format(key=config.keys[key]),
                'text': '\nWrong fingerprint\n{key[fingerprint]}\n\nExiting!'.format(key=config.keys[key]),
            }
            exit(info)

    # Add developers keys
    try:
        sh.gpg('--import', 'qubes-developers-keys.asc')
    except sh.ErrorReturnCode, err:
        exit('Unable to import Qubes developer keys (qubes-developers-keys.asc). Please install them manually.\n{0}'.format(err))

    return True


def dialog_verify_keys(**info):
    _info = {
        'title':  'Add Keys',
        'width': 60,
        'height': 8,
        'default_button': 'yes',
        'text': '',
    }
    _info.update(info)
    if dialog.yesno(**_info) == dialog.OK:
        return True

    exit('User aborted setup: Exiting setup since keys can not be installed')
    return False


class Setup(object):
    ''''''
    def __init__(self, **kwargs):
        self.kwargs = kwargs

        ## Load external data such as list of keys and repos
        self.config = Config(kwargs['config_filename'], **kwargs)
        self.config.load()

    def __call__(self):
        ## Copy example-configs/template.conf to builder.conf if
        ## the configuration file does not yet exist
        self.create_builder_conf(force=False)

        ## Check / Install Keys
        ## set force value to 'force' to force re-download and verify
        self.verify_keys(force=False)

        ## Choose release version
        ## Soft link 'examples/templates.conf' to 'builder.conf'
        self.config.release = self.set_release(force=True)

        ## Parse the existing makefiles to obtain values needed for setup to provide
        ## required options to build new configuration file
        self.config.parse_makefiles()

        ## Prompt for selection of base repo to use for build
        self.config.git_prefix = self.set_repo()

        ## Choose if user has git ssh (commit) or http access to private repos
        if os.path.exists(self.config.conf_override):
            self.config.ssh_access = self.set_ssh_access()

        ## Choose to build a complete system or templates only
        self.config.template_only = dialog_template_only(self.config.template_only)

        ## Select which templates to build (DISTS_VM)
        self.config.dists_vm_selected = self.set_dists()

        ## TODO: Prompt after DISTS_VM selected to prompt for BUILDER-debian, etc
        ## Choose BUILDER_PLUGINS

        ## Write setup.conf
        self.config.write_configuration()

    def gpg_verify_key(self, key):
        key_data = self.config.keys.get(key, None)
        if not key:
            return False
        verified = False

        try:
            text = sh.gpg('--with-colons', '--fingerprint', key).strip()
        except sh.ErrorReturnCode, err:
            return False

        for fingerprint in text.split('\n'):
            if fingerprint.startswith(u'fpr:') and fingerprint == self.config.keys[key]['verify']:
                verified = True
                break

        if not verified:
            print sh.gpg('--fingerprint', key)
            return False

        return verified

    def verify_keys(self, force=False):
        for key in self.config.keys:
            try:
                text = sh.gpg('--list-key', key)
            except sh.ErrorReturnCode, err:
                # exit_code will be non-zero and will trigger installation and verification of keys
                pass

            if force or text.exit_code:
                info = {}
                if force:
                    info['text'] = u'{key[owner]} forced get.\n\nSelect "Yes" to re-add or "No" to exit'.format(key=self.config.keys[key])
                else:
                    info['text'] = u'{key[owner]} key does not exist.\n\nSelect "Yes" to add or "No" to exit'.format(key=self.config.keys[key])

                if not dialog_verify_keys(**info):
                    exit('User aborted setup: Exiting setup since keys can not be installed')

                # Receive key from keyserver
                else:
                    try:
                        text = sh.gpg('--keyserver', 'pgp.mit.edu', '--recv-keys', key)
                    except sh.ErrorReturnCode, err:
                        exit('Unable to receive keys from keyserver.  Try again later or install them manually')

            # Verify key on every run
            result = self.gpg_verify_key(key)
            if not result:
                exit({'title':  '{key[owner]} fingerprint failed!'.format(key=self.config.keys[key]),
                       'text': '\nWrong fingerprint\n{key[fingerprint]}\n\nExiting!'.format(key=self.config.keys[key]),})

        # Add developers keys
        try:
            sh.gpg('--import', 'qubes-developers-keys.asc')
        except sh.ErrorReturnCode, err:
            exit('Unable to import Qubes developer keys (qubes-developers-keys.asc). Please install them manually.\n{0}'.format(err))

        return True

    def create_builder_conf(self, force=False):
        '''Copies example-configs/template.conf to builder.conf
        '''
        if not os.path.exists(self.config.conf_builder) or force:
            try:
                if os.path.exists(self.config.conf_builder) and force:
                    os.remove(self.config.conf_builder)

                shutil.copy2(self.config.conf_template, self.config.conf_builder)

                # ABOUT
                replace = ReplaceInplace(self.config.conf_builder)
                replace.add(**{
                    'replace': r'@echo "templates.conf"',
                    'text': r'@echo "builder.conf"',
                    })
                replace.start()
            except IOError, err:
                exit(err)

        return self.config.conf_builder

    def set_release(self, force=False):
        '''Select release version of Qubes to build.
        '''
        try:
            release = sh.make('-C', self.config.dir_builder, '-B', 'release', '--quiet').strip()
        except sh.ErrorReturnCode, err:
            print err
            pass

        return dialog_release(release or '3')

    def set_repo(self):
        '''Set repo prefix.
        '''
        choices = []
        default_set = False
        full_prefix = '{0}/{1}'.format(self.config.git_baseurl, self.config.git_prefix)

        for index, repo in self.config.repos.items():
            toggle = full_prefix.endswith(repo['prefix'])
            if toggle:
                default_set = True
            choices.append( (repo['prefix'], repo['description'], toggle) )

        choices.insert(0, (self.config.git_prefix_default, 'Stable - Default Repo', not default_set) )

        return dialog_repo(choices)

    def set_ssh_access(self):
        '''Set GIT_BASEURL and GIT_PREFIX to allow ssh (write) access to repo.
         Convert:
           `GIT_BASEURL` from `git://github.com` to `git@github.com:repo`
         - and -
           `GIT_PREFIX` from `repo/qubes-` to `qubes-`
        '''
        ssh_access = dialog_ssh_access(self.config.ssh_access)
        ssh_access = 1 if ssh_access else 0

        if ssh_access:
            if '/' in self.config.git_prefix:
                repo, prefix = self.config.git_prefix.split('/')
                self.config.git_prefix = prefix

        # Re-write baseurl depending on ssh_access mode
        baseurl = re.match(r'^(.*//|.*@)(.*(?=[:])|.*)([:].*|)', self.config.git_baseurl)
        if ssh_access:
            self.config.git_baseurl = 'git@{0}:{1}'.format(baseurl.group(2), repo)
        else:
            self.config.git_baseurl = 'https://{0}'.format(baseurl.group(2))

        return ssh_access

    def set_dists(self):
        ''''''
        choices = []
        helper = {}
        for dist in self.config.dists_vm_all:
            alias = self.config.template_aliases.get(dist, '')
            aliasr = self.config.template_aliases_reversed.get(dist, '')
            label = self.config.template_labels.get(alias or dist, '')

            tag = aliasr or dist
            item = label
            help = dist if dist != tag else ''

            helper[tag] = dedent('''\
            Distribution: {0}
            Template Label: {1}
            Template Alias: {2}
            ''').format(tag, item, help)

            if help:
                help = 'Alias value: {0}'.format(help)

            choices.append( (tag, item, dist in self.config.dists_vm_selected, help) )

        return dialog_dists(choices, helper)


class Config(object):
    ''''''
    MARKER = object()

    _makefile_vars = {
        'about':                     '',
        'release':                   0 ,
        'ssh_access':                0 ,
        'template_only':             0 ,
        'override_source':           '',
        'git_baseurl':               '',
        'git_prefix':                '',
        'git_prefix_default':        '',
        'dist_dom0_selected':        '',
        'dists_vm_all':              [],
        'dists_vm_selected':         [],
        'template_aliases':          [],
        'template_aliases_reversed': [],
        'template_labels':           [],
        'template_labels_reversed':  [],
        }

    def __init__(self, filename, **options):
        self.filename = filename
        self.options = options

        self.parser = ConfigParser()
        self.parser.add_section('makefile')
        self.sections = []
        self.keys = collections.OrderedDict()
        self.repos = collections.OrderedDict()

        self._init_makefile_vars()

        self.dir_builder = self.options.get('dir_builder', os.path.abspath(os.path.curdir))
        self.dir_configurations = os.path.join(self.dir_builder, 'example-configs')
        self.conf_template = os.path.join(self.dir_configurations, 'templates.conf')
        self.conf_override = os.path.join(self.dir_builder, 'override.conf')
        self.conf_builder = os.path.join(self.dir_builder, 'builder.conf')

    def _init_makefile_vars(self):
        for key, value in self._makefile_vars.items():
            setattr(self, key, value)
        print

    def __getattribute__(self, name):
        return super(Config, self).__getattribute__(name)

    def __setattr__(self, name, value):
        if name in self._makefile_vars:
            default = self._makefile_vars[name]
            if type(value) != type(default):
                try:
                    if isinstance(default, types.BooleanType):
                        value = bool(value)
                    elif isinstance(default, types.IntType):
                        value = int(value)
                    elif isinstance(default, types.FloatType):
                        value = float(value)
                    elif isinstance(default, types.ListType):
                        if isinstance(value, types.StringTypes):
                            value = value.strip().split()
                except ValueError, err:
                    #exit('Invalid Makefile value: {0}={1}:\n\n{2}'.format(name, value, err))
                    value = default
            self.parser.set('makefile', name, value)
        return super(Config, self).__setattr__(name, value)

    def _get_section(self, section_name):
        adict = {}
        options = self.parser.options(section_name)
        for option in options:
            try:
                print option
                print self.parser.get(section_name, option)
                adict[option] = self.parser.get(section_name, option)
                #if adict[option] == -1:
                #    adict.pop(option, None)
            except:
                adict[option] = None
        return adict

    def load(self):
        self.parser.readfp(codecs.open(self.filename, 'r', 'utf8'))
        for section_name in self.parser.sections():
            section = self._get_section(section_name)
            if not section:
                continue
            if 'fingerprint' in section:
                self.keys[section_name] = {}
                section['id'] = section_name
                self.keys[section_name].update(section)
            elif 'repo' in section:
                self.repos[section['repo']] = section

    def overrides(self):
        '''Set up any branch specific override configurations.
        '''
        #--------------------------------------------------------------------------
        # See if a branch specific override configuration file exists
        #--------------------------------------------------------------------------
        branch = sh.git('rev-parse', '--abbrev-ref', 'HEAD').strip()
        override_target = self.conf_override
        override_source = None

        # Skip if overrides already exsits and is a regular file
        if not (os.path.exists(self.conf_override) and not os.path.islink(self.conf_override)):
            dir = self.dir_configurations
            override = os.path.basename(self.conf_override)

            patterns = []
            # Example: example-configs/r3-feature_branch-override.conf
            patterns.append('{0}/r{1}-{2}-{3}'.format(dir, self.release, branch, override))

            # Example: example-configs/feature_branch-override.conf
            patterns.append('{0}/{1}-{2}'.format(dir, branch, override))

            # Example: example-configs/override.conf
            patterns.append('{0}/{1}'.format(dir, override))

            for pattern in patterns:
                if os.path.exists(pattern):
                    override_source = pattern
                    break

            if override_source:
                # If override_target alreaady exists (it is a link or we would not be here)
                # display a confirmation dialog to link if not currently linked to override_source
                if not os.readlink(override_target) == override_source:
                    result = dialog_override(override_source)

                    # Soft link override_source to override_target if user confirmed override
                    if result:
                        soft_link(override_source, override_target)
                    else:
                        override_source = None

        elif os.path.exists(self.conf_override):
            override_source = self.conf_override

        self.override_source = override_source

    def parse_makefiles(self):
        '''
        '''
        from sh import make
        env = os.environ.copy()
        make = make.bake('--always-make', '--quiet', 'get-var', directory=self.dir_builder, _env=env)

        # Get variables from Makefile INCLUDING setup.conf Makefile
        try:
            env['GET_VAR'] = 'SSH_ACCESS'
            self.ssh_access = make().strip()

            env['GET_VAR'] = 'TEMPLATE_ONLY'
            self.template_only = make().strip()

            env['GET_VAR'] = 'GIT_BASEURL'
            self.git_baseurl = make().strip()

            env['GET_VAR'] = 'GIT_PREFIX'
            self.git_prefix = make().strip()

            env['GET_VAR'] = 'DISTS_VM'
            self.dists_vm_selected = make().strip().split()
        except sh.ErrorReturnCode, err:
            exit('Error parsing Makefile): {0}'.format(err))

        env['GET_VAR'] = 'GIT_PREFIX'
        self.git_prefix_default= make().strip()

        # Set up any branch specific override configurations
        self.overrides()

        # Get variables from Makefile NOT INCLDING setup.conf Makefile
        # SELECTED_DISTS_VM=${SELECTED_DISTS_VM-( $(GET_VAR=DIST_DOM0 make get-var) )}
        # DISTS_VM=( $(SETUP_MODE=1 GET_VAR=DISTS_VM make get-var) )
        # ABOUT=($(make -B about))
        try:
            env['GET_VAR'] = 'DIST_DOM0'
            self.dist_dom0_selected = make().strip().split()

            env['SETUP_MODE'] = '1'
            env['GET_VAR'] = 'DISTS_VM'
            self.dists_vm_all = make().strip().split()

            env['GET_VAR'] = 'TEMPLATE_ALIAS'
            aliases = make().strip().split()
            self.template_aliases = dict([(item.split(':')) for item in aliases])
            self.template_aliases_reversed = dict([(value, key) for key, value in self.template_aliases.items()])

            env['GET_VAR'] = 'TEMPLATE_LABEL'
            labels = make().strip().split()
            self.template_labels = dict([(item.split(':')) for item in labels])
            self.template_labels_reversed = dict([(value, key) for key, value in self.template_labels.items()])

            self.about = sh.make('--always-make', '--quiet', 'about', directory=self.dir_builder)
        except sh.ErrorReturnCode, err:
            pass

    def write_configuration(self):
        '''Write setup configuration file to setup.conf.
        '''
        replace = ReplaceInplace(self.conf_builder)
        dists_vm = ''
        text = ''

        ### -- INFO -----------------------------------------------------------
        # Format about
        info = '''\
            ################################################################################
            #
            # Qubes Release: {self[release]}
            # Source Prefix: {self[git_prefix]} (repo)
            #
            # Master Configuration File(s):
            # setup.conf {about}
            #
            # builder.conf copied from:
            # {self[conf_template]}
            #
            ################################################################################
            '''.format(about=' '.join(self.about.split()), self=vars(self))

        ### -- DISTS_VM -------------------------------------------------------
        for dist in self.dists_vm_selected:
            dists_vm += 'DISTS_VM += {0}\n{1}'.format(dist, '              ')
        dists_vm = dists_vm.strip()

        dists = '''\
            ifneq "$(SETUP_MODE)" "1"

              # Enabled DISTS_VMs
              DISTS_VM :=
              {dists_vm}

            endif
            '''.format(dists_vm=dists_vm, self=vars(self))

        # INFO
        replace.add(**{
            'insert_after': r'.*[[]=setup insert start 01=[]]',
            'insert_until': r'.*[[]=setup insert stop 01=[]]',
            'text': dedent(info).rstrip('\n'),
            })

        # DISTS_VM
        replace.add(**{
            'insert_after': r'.*[[]=setup insert start 05=[]]',
            'insert_until': r'.*[[]=setup insert stop 05=[]]',
            'text': dedent(dists).rstrip('\n'),
            })

        # RELEASE
        replace.add(**{
            'replace': r'RELEASE[ ]*[?:]?=[ ]*[\d]',
            'text': r'RELEASE := {0}'.format(self.release),
            })

        # SSH_ACCESS
        replace.add(**{
            'replace': r'SSH_ACCESS[ ]*[?:]?=[ ]*[\d]',
            'text': r'SSH_ACCESS := {0}'.format(self.ssh_access),
            })

        # GIT_BASEURL
        replace.add(**{
            'replace': r'GIT_BASEURL[ ]*[?:]?=[ ]*.*',
            'text': r'GIT_BASEURL := {0}'.format(self.git_baseurl),
            })

        # GIT_PREFIX
        replace.add(**{
            'replace': r'GIT_PREFIX[ ]*[?:]?=[ ]*.*',
            'text': r'GIT_PREFIX := {0}'.format(self.git_prefix),
            })

        # TEMPLATE_ONLY
        replace.add(**{
            'replace': r'TEMPLATE_ONLY[ ]*[?:]?=[ ]*.*',
            'text': r'TEMPLATE_ONLY ?= {0}'.format(self.template_only),
            })

        # OVERRIDE
        if self.override_source:
            override = r'-include override.conf'
        else:
            override = r'-include override.conf'

        replace.add(**{
            'replace': r'.*-include[ ]+override.conf',
            'text': r'{0}'.format(override),
            })

        # Start the search and replace process on the configuration file
        replace.start()

        ansi =  ANSIColor()
        display_configuration(self.conf_builder)
        info = '\nNew configuration file written to: {0}\n'.format(self.conf_builder)

        install_qubes = '''
            Complete Qubes Build Steps
            --------------------------
            make get-sources
            make qubes
            make iso
            '''

        install_qubes_vm = '''
            Template Only Build Steps
            -------------------------
            make get-sources
            make template-modules
            make template
            '''

        if self.template_only:
            info += dedent(install_qubes_vm)
        else:
            info += dedent(install_qubes)
        print '{ansi[green]}{0}{ansi[normal]}'.format(info, ansi=ansi)


class ReplaceInplace(object):
    def __init__(self, filename):
        self.filename = filename
        self.rules = {}

    defaults =  {
        # key to use to match line
        'match_key': None,

        # text will be inserted below pattern matched line. Keeps pattern.
        'insert_after': None,

        # all text before this line will be removed.  Keeps pattern
        # if value is `None`, stop insert mode after initial insert
        'insert_until': None,

        'replace': None,

        'text': None,
        'find': None,
        'start_line': None,
        'stop_line': None,
        }

    def add(self, **kwargs):
        import copy
        default = copy.deepcopy(self.defaults)
        default.update(kwargs)

        if default['insert_after']:
            default['insert_after'] = re.compile(r'{0}'.format(default['insert_after']))
            default['match_key'] = 'insert_after'

            if default['insert_until']:
                default['insert_until'] = re.compile(r'{0}'.format(default['insert_until']))

        elif default['replace']:
            default['replace'] = re.compile(r'{0}'.format(default['replace']))
            default['match_key'] = 'replace'

        match_key = default[default['match_key']]
        self.rules[match_key] = default

    def start(self):
        import fileinput
        insert_mode = False
        stop = []

        for line in fileinput.input(self.filename, inplace=True, backup='.bak'):
            line =  line.rstrip('\n')
            for rule in self.rules:
                if rule.search(line):
                    if self.rules[rule]['match_key'] == 'insert_after':
                        insert_mode = True
                        stop.append(self.rules[rule]['insert_until'])
                        print line
                        print self.rules[rule]['text']
                    elif self.rules[rule]['match_key'] == 'replace':
                        line = rule.sub(self.rules[rule]['text'], line)

            for rule in stop:
                if re.match(rule, line):
                    stop.remove(rule)
                    insert_mode = False

            if not insert_mode:
                print line


def main(argv):
    parser = argparse.ArgumentParser()
    #subparsers = parser.add_subparsers(dest='subparser', help='commands')

    parser.add_argument( '--dialog-release', action='store', default='3', help='Display the Choose Release Dialog' )
    parser.add_argument( '--dir', dest='dir_builder', action='store', default=None,
                         help='Location path of qubes-builder base directory' )
    parser.add_argument( '-c', dest='config_filename', action='store', default='.setup.data',
                         help='Setup configuration file' )

    args = vars(parser.parse_args())

    # XXX: TEMP for debugging
    args['dir_builder'] = '/home/user/qubes'

    setup = Setup(**args)
    setup()
    #exit()


if __name__ == '__main__':
    main(sys.argv)
    sys.exit(0)
