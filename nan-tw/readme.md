bash -c "ss -lptn 'sport = :9874' 2>/dev/null; echo '---'; ps aux | grep -i webui.py | grep -v grep"
unset http_proxy https_proxy all_proxy HTTP_PROXY HTTPS_PROXY ALL_PROXY
export no_proxy="localhost,127.0.0.1"
python webui.py 