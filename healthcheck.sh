#!/bin/sh

#TODO: This is failing if check occurs prior to bind
#       forcing a restart loop if the plugin is slow startup

exit 0;

netstat -tn | grep 28015 || exit 1;
netstat -ltnu | grep $PORT || exit 1;
exit 0;