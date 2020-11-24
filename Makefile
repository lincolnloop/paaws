.PHONY: apppack.pyz
apppack.pyz:
	shiv -o $@ -e apppack.__main__.main -p "/usr/bin/env python3" --extend-pythonpath .
