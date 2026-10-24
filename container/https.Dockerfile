FROM caddy:2.10.2-alpine
# Listen on high container ports; the stock binary's file capability is unnecessary
# and prevents exec when every container capability is dropped.
RUN setcap -r /usr/bin/caddy
USER 1000:1000
