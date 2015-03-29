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

import sh

from ConfigParser import ConfigParser
from textwrap import dedent
from ansi import ANSIColor

locale.setlocale(locale.LC_ALL, '')
DIALOG = 'dialog'


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


def path_link(source, target):
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

    result = dialog.yesno(**{
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

    if result == dialog.OK:
        return '2'
    elif result == dialog.CANCEL:
        return '3'
    elif result == dialog.ESC:
        close('Escape key pressed. Exiting.')



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

            result = dialog.yesno(**{
                'title':  'Add Keys',
                'width': 60,
                'height': 8,
                'default_button': 'yes',
                'text': message,
            })

            if result != dialog.OK:
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
        #force = True
        #self.set_release(force)

        ## Parse the existing makefiles to obtain values needed for setup to provide
        ## required options to build new configuration file
        self.config.parse_makefiles()

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
            path_link(self.config.get_filename('conf_template'), self.config.get_filename('conf_builder'))

        self.config.release = release_selected
        return self.config.release



class Config(object):
    ''''''
    def __init__(self, filename, **options):
        self.filename = filename

        self.parser = ConfigParser()
        self.sections = []
        self.keys = collections.OrderedDict()
        self.repos = collections.OrderedDict()

        self.release = None

        self.options = options

    def get_filename(self, filename):
        dir_builder = self.options.get('dir_builder', os.path.abspath(os.path.curdir))
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

    def parse_makefiles(self):
        '''
        '''

        from sh import make
        env = os.environ.copy()
        #make.bake('-B', '-C', self.get_filename('dir_builder'), '--quiet', _env=env)
        make = make.bake('--always-make', '--quiet', 'get-var', directory=self.get_filename('dir_builder'), _env=env)

        #--------------------------------------------------------------------------
        # Get variables from Makefile INCLUDING setup.conf Makefile
        #--------------------------------------------------------------------------
        #SSH_ACCESS="$(GET_VAR=SSH_ACCESS make get-var)"
        #TEMPLATE_ONLY="$(GET_VAR=TEMPLATE_ONLY make get-var)"
        #GIT_PREFIX="$(GET_VAR=GIT_PREFIX make get-var)"

        try:
            env['GET_VAR'] = 'SSH_ACCESS'
            self.ssh_access = make().strip()

            env['GET_VAR'] = 'TEMPLATE_ONLY'
            self.template_only = make().strip()

            env['GET_VAR'] = 'GIT_PREFIX'
            self.git_prefix = make().strip()
        except sh.ErrorReturnCode, err:
            print err
            pass

        '''
        # Remove GIT_PREFIX from builder-release.conf so default prefix can be
        # determined
        if [ -e "${CONF_RELEASE}" ]; then
            sed -i 's/GIT_PREFIX/#GIT_PREFIX/' "${CONF_RELEASE}"
        fi
        DEFAULT_PREFIX="$(GET_VAR=GIT_PREFIX make get-var)"

        #--------------------------------------------------------------------------
        # Move setup.conf out of the way if it exists
        #--------------------------------------------------------------------------
        if [ -f "${CONF_FILE}" ]; then
            SELECTED_DISTS_VM=( $(GET_VAR=DISTS_VM make get-var) )
            mv "${CONF_FILE}" "${CONF_FILE_OLD}"
        fi

        #--------------------------------------------------------------------------
        # See if a branch specific override configuration file exists
        #--------------------------------------------------------------------------
        BRANCH="$(git rev-parse --abbrev-ref HEAD)"
        OVERRIDE_TARGET="./${CONF_OVERRIDE}"

        # Check for generic overrides only if 'override.conf' does not exist
        if [ "X${OVERRIDE_SOURCE}" == "X" ]; then

            # Example: example-configs/r3-feature_branch-override.conf
            if [ -e "${CONF_MASTER_DIR}/r${RELEASE}-${BRANCH}-${CONF_OVERRIDE}" ]; then
                OVERRIDE_SOURCE="${CONF_MASTER_DIR}/r${RELEASE}-${BRANCH}-${CONF_OVERRIDE}"

            # Example: example-configs/feature_branch-override.conf
            elif [ -e "${CONF_MASTER_DIR}/${BRANCH}-${CONF_OVERRIDE}" ]; then
                OVERRIDE_SOURCE="${CONF_MASTER_DIR}/${BRANCH}-${CONF_OVERRIDE}"

            # Example: example-configs/override.conf
            elif [ -e "${CONF_MASTER_DIR}/${CONF_OVERRIDE}" ]; then
                OVERRIDE_SOURCE="${CONF_MASTER_DIR}/${CONF_OVERRIDE}"
            fi
        fi

        # Check if a branch specific user override configuration file is available
        if [ -f "${OVERRIDE_SOURCE}" ] && [[ ! -a "${OVERRIDE_TARGET}" || -h "${OVERRIDE_TARGET}" ]]; then

            # Don't do anything is configuration file is already linked
            if [ "$(readlink -m ${OVERRIDE_SOURCE})" != "$(readlink -m ${CONF_OVERRIDE})" ]; then
                # Display 'Use Override Dialog'
                useOverrideConfiguration || unset OVERRIDE_SOURCE

                # Soft link the configuration file
                if [[ -n "${OVERRIDE_SOURCE}" ]]; then
                    ln -sf "${OVERRIDE_SOURCE}" "${OVERRIDE_TARGET}" || unset OVERRIDE_SOURCE

                    # Some type of linking error
                    if [[ -z "${OVERRIDE_SOURCE}" ]]; then
                        message="Could not set link to override configuration file!\n\nUsing defaults."
                        dialog --msgbox "${message}" 8 60
                    fi
                # Remove stale override link
                elif [ -h "${CONF_OVERRIDE}" ]; then
                    rm -f "${CONF_OVERRIDE}"
                fi
            fi

        else
            # If a soft-linked override exists, remove it, but don't delete any regular files
            if [ -h "${CONF_OVERRIDE}" ]; then
                rm -f "${CONF_OVERRIDE}"
            fi

            if [ -f "${CONF_OVERRIDE}" ]; then
                OVERRIDE_SOURCE="${CONF_OVERRIDE}"
            else
                unset OVERRIDE_SOURCE
            fi
        fi

        #--------------------------------------------------------------------------
        # Get variables from Makefile NOT INCLDING setup.conf Makefile
        #--------------------------------------------------------------------------
        SELECTED_DISTS_VM=${SELECTED_DISTS_VM-( $(GET_VAR=DIST_DOM0 make get-var) )}
        DISTS_VM=( $(SETUP_MODE=1 GET_VAR=DISTS_VM make get-var) )
        ABOUT=($(make -B about))
        '''


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


if __name__ == '__main__':
    main(sys.argv)
    sys.exit(0)
