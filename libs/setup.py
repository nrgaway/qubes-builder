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

from __future__ import unicode_literals
import sys
import os
import locale
import codecs
import argparse
import collections
import shutil

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

def close(message=None):
    '''Function to exit.  Maybe restoring some files before exiting.
    '''
    if message:
        info = {
            'title':  'System Exit!',
            'width': 60,
            'height': 8,
            'text': message
        }
        if isinstance(message, collections.Mapping):
            info.update(message)
        dialog.infobox(**info)

    # Restore original setup.conf
    if os.path.exists(Config.get_filename('conf_file_old')):
        shutil.move(Config.get_filename('conf_file_old'), Config.get_filename('conf_file'))

    # Restore original GIT_PREFIX
    if os.path.exists(Config.get_filename('conf_release')):
        sh.sed('-i', 's/#GIT_PREFIX/GIT_PREFIX/', Config.get_filename('conf_release'))

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
        close()

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


def soft_link(source, target):
    '''Attempt to soft-link a file.  Exit with message on failure.
    '''
    try:
        if os.path.exists(target) and not os.path.islink(target):
            message = 'Setup will not over-write regular files that are not soft-linked.'
            close('Error linking:\n{0} to {1}\n\n{2}'.format(source, target, message))

        if os.path.exists(source):
            if os.path.exists(target):
                os.remove(target)
            os.symlink(source, target)
        else:
            message = 'Target file does not exist and therefore cannot be linked.'
            close('Error linking:\n{0} to {1}\n\n{2}'.format(source, target, message))
    except OSError, e:
        close('Error linking:\n{0} to {1}\n\n{2}.'.format(source, target, e.strerror))


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
        close('Escape key pressed. Exiting.')


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
        close('User aborted setup.')


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
            close('User aborted setup.')

        elif code == dialog.ESC:
            close('User aborted setup.')

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
        close('Escape key pressed. Exiting.')


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
        close('Escape key pressed. Exiting.')


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
                close('User aborted setup: Exiting setup since keys can not be installed')

            # Receive key from keyserver
            else:
                try:
                    text = sh.gpg('--keyserver', 'pgp.mit.edu', '--recv-keys', key)
                except sh.ErrorReturnCode, err:
                    close('Unable to receive keys from keyserver.  Try again later or install them manually')

        # Verify key on every run
        result = self.gpg_verify_key(key)
        if not result:
            info = {
                'title':  '{key[owner]} fingerprint failed!'.format(key=config.keys[key]),
                'text': '\nWrong fingerprint\n{key[fingerprint]}\n\nExiting!'.format(key=config.keys[key]),
            }
            close(info)

    # Add developers keys
    try:
        sh.gpg('--import', 'qubes-developers-keys.asc')
    except sh.ErrorReturnCode, err:
        close('Unable to import Qubes developer keys (qubes-developers-keys.asc). Please install them manually.\n{0}'.format(err))

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

    close('User aborted setup: Exiting setup since keys can not be installed')
    return False


class Setup(object):
    ''''''
    def __init__(self, **kwargs):
        self.kwargs = kwargs

        ## Load external data such as list of keys and repos
        self.config = Config(kwargs['config_filename'], **kwargs)
        self.config.load()

    def __call__(self):
        ## Check / Install Keys
        ## set force value to 'force' to force re-download and verify
        #force = True
        #self.verify_keys(force)

        ## Choose release version
        ## Soft link 'examples/templates.conf' to 'builder.conf'
        force = True
        self.config.release = self.set_release(force)

        ## Parse the existing makefiles to obtain values needed for setup to provide
        ## required options to build new configuration file
        self.config.parse_makefiles()

        ## Prompt for selection of base repo to use for build
        self.config.git_prefix = self.set_repo()

        ## TODO:
        ## Choose BUILDER_PLUGINS

        ## Choose if user has git ssh (commit) or http access to private repos
        ## - Only asked if there is an override.conf configuration file to prevent
        ##   access denied errors
        ##
        ## Example of override.conf to allow ssh and http access based on user selection:
        ##
        ## GITHUB_PREFIX = $(word $(SSH_ACCESS), http://github.com/private_repo/qubes- git@github.com:private_repo/qubes-)
        ## RELEASE_INDEX = $(shell echo "$(RELEASE)-1" | bc)
        ##
        ## [==- 'gui-agent-linux'==========================================================
        ## [==- defaults: [R2:release2, R3:master]
        ## [===============================================================================
        ## GIT_URL_gui_agent_linux = $(GITHUB_PREFIX)/gui-agent-linux.git
        ## BRANCH_gui_agent_linux = $(word $(RELEASE_INDEX), release2 master)
        if os.path.exists(self.config.get_filename('conf_override')):
            self.config.ssh_access = dialog_ssh_access(self.config.ssh_access)

        ## Choose to build a complete system or templates only
        self.config.template_only = dialog_template_only(self.config.template_only)

        # Select which templates to build (DISTS_VM)
        self.config.selected_dists_vm = self.set_dists()

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
                    close('User aborted setup: Exiting setup since keys can not be installed')

                # Receive key from keyserver
                else:
                    try:
                        text = sh.gpg('--keyserver', 'pgp.mit.edu', '--recv-keys', key)
                    except sh.ErrorReturnCode, err:
                        close('Unable to receive keys from keyserver.  Try again later or install them manually')

            # Verify key on every run
            result = self.gpg_verify_key(key)
            if not result:
                close({'title':  '{key[owner]} fingerprint failed!'.format(key=self.config.keys[key]),
                       'text': '\nWrong fingerprint\n{key[fingerprint]}\n\nExiting!'.format(key=self.config.keys[key]),})

        # Add developers keys
        try:
            sh.gpg('--import', 'qubes-developers-keys.asc')
        except sh.ErrorReturnCode, err:
            close('Unable to import Qubes developer keys (qubes-developers-keys.asc). Please install them manually.\n{0}'.format(err))

        return True

    def set_release(self, force=False):
        '''Select release version of Qubes to build.
        '''
        release_original = None
        if os.path.exists(self.config.get_filename('conf_builder')):
            try:
                release_original = sh.make('-C', self.config.get_filename('dir_builder'), '-B', 'release', '--quiet').strip()
            except sh.ErrorReturnCode, err:
                print err
                pass

        release_selected = dialog_release(release_original or '3')

        if release_original != release_selected:
            soft_link(self.config.get_filename('conf_template'), self.config.get_filename('conf_builder'))

        return release_selected

    def set_repo(self):
        '''Set repo prefix.
        '''
        counter=1
        choices = []

        toggle = self.config.git_prefix == self.config.default_prefix
        choices.append( (self.config.default_prefix, 'Stable - Default Repo', toggle) )

        for index, repo in self.config.repos.items():
            toggle = self.config.git_prefix == repo['prefix']
            choices.append( (repo['prefix'], repo['description'], toggle) )

        return dialog_repo(choices)

    def set_dists(self):
        ''''''
        choices = []
        helper = {}
        for dist in self.config.all_dists_vm:
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

            choices.append( (tag, item, dist in self.config.selected_dists_vm, help) )

        return dialog_dists(choices, helper)


class Config(object):
    ''''''
    options = None

    def __init__(self, filename, **options):
        self.filename = filename

        self.parser = ConfigParser()
        self.sections = []
        self.keys = collections.OrderedDict()
        self.repos = collections.OrderedDict()

        self.release = None

        self.options = options
        Config.options = options

        self.override_source = None
        self.default_prefix= None
        self.ssh_access = None
        self.template_only = None
        self.git_prefix = None
        self.default_prefix= None
        self.all_dists_vm = None
        self.selected_dist_dom0 = None
        self.selected_dists_vm = None
        self.template_only = None
        self.template_aliases = None
        self.template_aliases_reversed = None
        self.template_labels = None
        self.template_labels_reversed = None
        self.about = None

    @classmethod
    def get_filename(cls, filename):
        dir_builder = cls.options.get('dir_builder', os.path.abspath(os.path.curdir))
        dir_configurations = os.path.join(dir_builder, 'example-configs')

        filenames = {
            'dir_builder':        dir_builder,
            'dir_configurations': dir_configurations,
            'conf_template':      os.path.join(dir_configurations, 'templates.conf'),
            'conf_file':          os.path.join(dir_builder, 'setup.conf'),
            'conf_file_old':      os.path.join(dir_builder, 'setup.conf.old'),
            'conf_override':      os.path.join(dir_builder, 'override.conf'),
            'conf_release':       os.path.join(dir_builder, 'builder-release.conf'),
            'conf_builder':       os.path.join(dir_builder, 'builder.conf'),
        }

        return filenames.get(filename, None)

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
        override_target = self.get_filename('conf_override')
        override_source = None

        # Skip if overrides already exsits and is a regular file
        if not (os.path.exists(self.get_filename('conf_override')) and os.path.islink(self.get_filename('conf_override'))):
            dir = self.get_filename('dir_configurations')
            override = os.path.basename(self.get_filename('conf_override'))

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

        self.override_source = override_source

    def parse_makefiles(self):
        '''
        '''
        from sh import make
        env = os.environ.copy()
        make = make.bake('--always-make', '--quiet', 'get-var', directory=self.get_filename('dir_builder'), _env=env)

        # Get variables from Makefile INCLUDING setup.conf Makefile
        try:
            env['GET_VAR'] = 'SSH_ACCESS'
            self.ssh_access = make().strip()

            env['GET_VAR'] = 'TEMPLATE_ONLY'
            self.template_only = make().strip()

            env['GET_VAR'] = 'GIT_PREFIX'
            self.git_prefix = make().strip()

            env['GET_VAR'] = 'DISTS_VM'
            self.selected_dists_vm = make().strip().split()
        except sh.ErrorReturnCode, err:
            pass

        # Remove GIT_PREFIX from builder-release.conf so default prefix can be
        # determined
        if os.path.exists(self.get_filename('conf_release')):
            sh.sed('-i', 's/GIT_PREFIX/#GIT_PREFIX/', self.get_filename('conf_release'))
        env['GET_VAR'] = 'GIT_PREFIX'
        self.default_prefix= make().strip()

        # Move setup.conf out of the way if it exists
        if os.path.exists(Config.get_filename('conf_file')):
            shutil.move(Config.get_filename('conf_file'), Config.get_filename('conf_file_old'))

        # Set up any branch specific override configurations
        self.overrides()

        # Get variables from Makefile NOT INCLDING setup.conf Makefile
        # SELECTED_DISTS_VM=${SELECTED_DISTS_VM-( $(GET_VAR=DIST_DOM0 make get-var) )}
        # DISTS_VM=( $(SETUP_MODE=1 GET_VAR=DISTS_VM make get-var) )
        # ABOUT=($(make -B about))
        try:
            env['GET_VAR'] = 'DIST_DOM0'
            self.selected_dist_dom0 = make().strip().split()

            env['SETUP_MODE'] = '1'
            env['GET_VAR'] = 'DISTS_VM'
            self.all_dists_vm = make().strip().split()

            env['GET_VAR'] = 'TEMPLATE_ALIAS'
            aliases = make().strip().split()
            self.template_aliases = dict([(item.split(':')) for item in aliases])
            self.template_aliases_reversed = dict([(value, key) for key, value in self.template_aliases.items()])

            env['GET_VAR'] = 'TEMPLATE_LABEL'
            labels = make().strip().split()
            self.template_labels = dict([(item.split(':')) for item in labels])
            self.template_labels_reversed = dict([(value, key) for key, value in self.template_labels.items()])

            self.about = sh.make('--always-make', '--quiet', 'about', directory=self.get_filename('dir_builder'))
        except sh.ErrorReturnCode, err:
            pass


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
    close('Setup Complete.')


if __name__ == '__main__':
    main(sys.argv)
    sys.exit(0)
