#!/usr/bin/env python27
# -*- coding: utf-8 -*- 
__author__ = 'liant'
import os
from google.appengine.ext import vendor

# Add any libraries installed in the "lib" folder.
vendor.add('lib')

#
# Enable ctypes on dev appserver so we get proper flask tracebacks.
# From http://jinja.pocoo.org/docs/dev/faq/#my-tracebacks-look-weird-what-s-happening
# and http://stackoverflow.com/questions/3086091/debug-jinja2-in-google-app-engine
PRODUCTION_MODE = not os.environ.get(
    'SERVER_SOFTWARE', 'Development').startswith('Development')
if not PRODUCTION_MODE:
    from google.appengine.tools.devappserver2.python import sandbox

    sandbox._WHITE_LIST_C_MODULES += ['_ctypes', 'gestalt']
    import os
    import sys

    if os.name == 'nt':
        os.name = None
        sys.platform = ''
