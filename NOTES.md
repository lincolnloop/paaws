
Run container until all users have logged out. Timeout in 12h:
```bash
sh -c 'STOP=$(($(date +%s)+43200)); sleep 60; while true; do  PROCS="$(ls /proc | grep \[0-9\] | wc -l)"; test "$PROCS" -lt "6" && exit; test "$STOP" -lt "$(date +%s)" && exit; sleep 30; done'
```



commands:

* metrics console

# TODO

* make shell exit on disconnect more robust
