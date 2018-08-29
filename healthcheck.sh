#!/bin/sh

netstat | grep 28015 || exit 1
netstat -ltnu | grep $PORT || exit 1