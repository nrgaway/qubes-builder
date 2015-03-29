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


def dialog_release(release):
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


def gpg_verify_key(config, key):
    key_data = config.keys.get(key, None)
    if not key:
        return False
    verified = False

    try:
        text = sh.gpg('--with-colons', '--fingerprint', key).strip()
    except sh.ErrorReturnCode:
        return False

    # XXX: Incorrect formula most likely; test
    # if [ "${line:$[${#line} - ${#1} -1]:-1}" != "${1}"]:
    for fingerprint in text.split('\n'):
        if fingerprint.startswith(u'fpr:') and fingerprint == config.keys[key]['verify']:
            verified = True
            break

    if not verified:
        print sh.gpg('--fingerprint', key)
        return False

    return verified


def dialog_verify_keys(config, force=False):
    for key in config.keys:
        try:
            text = sh.gpg('--list-key', key)
        except sh.ErrorReturnCode:
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
                except sh.ErrorReturnCode:
                    close('Unable to receive keys from keyserver.  Try again later or install them manually')

        # Verify key on every run
        result = gpg_verify_key(config, key)
        if not result:
            info = {
                'title':  '{key[owner]} fingerprint failed!'.format(key=config.keys[key]),
                'text': '\nWrong fingerprint\n{key[fingerprint]}\n\nExiting!'.format(key=config.keys[key]),
            }
            close(info)

    # Add developers keys
    try:
        sh.gpg('--import', 'qubes-developers-keys.asc')
    except sh.ErrorReturnCode, message:
        close('Unable to import Qubes developer keys (qubes-developers-keys.asc). Please install them manually.\n{0}'.format(message))

    return True


class Config(object):
    ''''''
    def __init__(self, filename):
        self.filename = filename
        self.parser = ConfigParser()
        self.sections = []
        self.keys = collections.OrderedDict()
        self.repos = collections.OrderedDict()

    def get_section(self, section_name):
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
            section = self.get_section(section_name)
            if not section:
                continue
            if 'fingerprint' in section:
                self.keys[section_name] = {}
                section['id'] = section_name
                self.keys[section_name].update(section)
            elif 'repo' in section:
                self.repos[section['repo']] = section


def main(argv):
    parser = argparse.ArgumentParser()
    #subparsers = parser.add_subparsers(dest='subparser', help='commands')

    parser.add_argument( '--dialog-release', action='store', default='3', help='Display the Choose Release Dialog' )
    parser.add_argument( '-c', dest='config_filename', action='store', default='.setup.data',
                         help='Setup configuration file' )

    args = vars(parser.parse_args())

    # ------------------------------------------------------------------------------
    # Load external data such as list of keys and repos
    # ------------------------------------------------------------------------------
    config = Config(args['config_filename'])
    config.load()

    # ------------------------------------------------------------------------------
    # Check / Install Keys
    # ------------------------------------------------------------------------------
    # set force value to 'force' to force re-download and verify
    force = True
    dialog_verify_keys(config, force)

    #------------------------------------------------------------------------------
    # Prompt for selection of base repo to use for build
    #------------------------------------------------------------------------------
    #if args['dialog_release']:
    #    release = dialog_release(args['dialog_release'])
    #    sys.exit(str(release))

if __name__ == '__main__':
    main(sys.argv)
    sys.exit(0)
