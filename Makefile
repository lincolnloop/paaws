.PHONY: paaws.pyz
paaws.pyz:
	shiv -o $@ -e paaws.__main__.main -p "/usr/bin/env python3" --extend-pythonpath .
