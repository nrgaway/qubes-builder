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
import argparse

from textwrap import dedent

from dialog import Dialog

# This is almost always a good thing to do at the beginning of your programs.
locale.setlocale(locale.LC_ALL, '')

# Initialize a dialog.Dialog instance
dialog = Dialog(dialog='dialog')
dialog.set_background_title("Qubes Builder Configuration Utility")

'''
installDialog() {
    if [ ! -f "$DIALOG" ]; then
        _dialog="${DIALOG##*/}"
        info "${red}${_dialog}${blue} is not installed and required for setup."
        echo
        read -p "Enter 'Y' to install now or anything else to quit [YyNnQq]: " -r
        if [[ ! $REPLY =~ ^[]|[Yy]$ ]] && [[ -n $REPLY ]]; then
            error "You selected not to install ${blue}${_dialog}${red} and therefore setup must now exit"
            error "Exiting!"
            exit 1
        fi

        exec sudo yum -y install ${_dialog} 2>&1 > /dev/null &
        pid=$!

        info "Waiting for ${red}${_dialog}${blue} to install"
        while ps -p$pid 2>&1 > /dev/null; do
            printf "${red}.${reset}"
            sleep 1
        done
        echo
    fi
}
'''


def close():
    '''Function to exit.  Maybe restoring some files before exiting.
    '''
    sys.exit()


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
        close()


def main(argv):
    parser = argparse.ArgumentParser()
    #subparsers = parser.add_subparsers(dest='subparser', help='commands')

    parser.add_argument( '--dialog-release',
                         action='store',
                         default='3',
                         help='Display the Choose Release Dialog'
                         )

    args = vars(parser.parse_args())

    if args['dialog_release']:
        release = dialog_release(args['dialog_release'])
        sys.exit(str(release))

if __name__ == '__main__':
    main(sys.argv)
    sys.exit(0)
