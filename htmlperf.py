import sys
import optparse
import os
import gc
import time
import subprocess
import urllib
import re

sample_data = os.path.join(os.path.dirname(__file__), 'sample-data', 'python.org')

type_map = {}

class LxmlType(object):

    name = 'lxml'
    description = 'lxml.html'

    def __init__(self):
        from lxml.html import parse, tostring
        self.parse = parse
        self.tostring = tostring

    def parse_file(self, filename):
        parser = lxml.etree.XMLParser(load_dtd=True)
        # Can't use a SAX interface because lxml's implementation chokes
        # when entities are left unresolved. Oops.
        f = open(filename, 'rb')
        for node in lxml.etree.parse(f, parser).iter():
            pass

    def serialize(self, doc):
        return self.tostring(doc)

type_map['lxml'] = LxmlType

from xml.sax.handler import ContentHandler
from lxml.sax import saxify
import lxml.etree
class SouptestSaxHandler(ContentHandler):
    
    def startElementNS(self, tagname, qname, attrs):
	pass

class LxmlSaxType(object):

    name = 'lxml_sax'
    description = 'lxml.html'

    def __init__(self):
        from lxml.html import parse, tostring
        self.parse = parse
        self.tostring = tostring

    def parse_file(self, filename):
        parser = lxml.etree.XMLParser(load_dtd=False)
        f = open(filename, 'rb')
        tree = lxml.etree.parse(f, parser)
        handler = SouptestSaxHandler()
        saxify(tree, handler)

    def serialize(self, doc):
        return self.tostring(doc)

type_map['lxml_sax'] = LxmlSaxType

from random import randint

def get_ps(expand=False):
    expansion = []
    char_length = range(1000)
    start_rss = None
    repeats = 1
    gc.collect()
    while 1:
        proc = subprocess.Popen(['ps', 'uww', '-p', str(os.getpid())], stdout=subprocess.PIPE)
        output, stderr = proc.communicate()
        parts = output.splitlines()[1].split()
        vsz = int(parts[4])
        rss = int(parts[5])
        if not expand:
            return vsz, rss, None
        if start_rss is not None and rss-start_rss > 10: # Added 10K
            break
        if start_rss is None:
            start_rss = rss
        repeats += 1
        #gc.collect()
        expansion.append(''.join([chr(randint(1, 255)) for i in char_length]))
        print 'Adding %s (%s->%s)' % (repeats, start_rss, rss)
    #print output
    adjust = repeats*(len(char_length)+4+4)/1024
    ## FIXME: should I do this?
    #adjust -= 10
    #adjust -= (rss-start_rss)
    if adjust < 0:
        print 'Somehow the adjustment would have added memory'
        print 'repeats=%s; length=%s; adjust=%s' % (repeats, len(char_length), adjust)
        adjust = 0
    return vsz, start_rss-adjust, adjust

def all_filenames(dir):
    paths = []
    for dirpath, dirnames, filenames in os.walk(dir):
        paths.extend([os.path.join(dirpath, fn) for fn in filenames
                      if fn.endswith('.xml')])
    return paths

def test_type(type, disable_gc, keep_docs, serialize, sample_data):
    print 'Testing %s' % type.description
    filenames = all_filenames(sample_data)
    size = 0
    for fn in filenames:
        size += os.stat(fn).st_size
    print 'Files: %s  Size: %sKb' % (len(filenames), size/1000)
    all_docs = []
    if not disable_gc:
        gc.disable()
    total_fn = len(filenames)
    segment = total_fn / 20
    if keep_docs:
        start_vsz, start_rss, dummy = get_ps()
    if serialize:
        for i, filename in enumerate(filenames):
            doc = type.parse_file(filename)
            all_docs.append(doc)
            i += 1
            if not i % segment or i == total_fn:
                sys.stdout.write('\r%5i/%5i   %i%%' % (
                    i, total_fn, 100.0*i/total_fn))
                sys.stdout.flush()
        sys.stdout.write('\nFinished parsing.')
        sys.stdout.flush()
    start = time.time()
    if serialize:
        for doc in all_docs:
            assert type.serialize(doc)
    else:
        for i, filename in enumerate(filenames):
            try:
                doc = type.parse_file(filename)
            except:
                print
                print 'Error in file %s' % filename
                raise
            if keep_docs:
                all_docs.append(doc)
            i += 1
            if not segment or i % segment or i == total_fn:
                sys.stdout.write('\r%5i/%5i   %i%%' % (
                    i, total_fn, 100.0*i/total_fn))
                sys.stdout.flush()
    end = time.time()
    gc.collect()
    print
    print 'done.'
    if keep_docs:
        end_vsz, end_rss, adjust = get_ps()
        print 'Increased VSZ/RSS:'
        print '%s%s: %6i  / %6i   (unused: %4i)' % (
            type.name, (15-len(type.name)) * ' ',
            end_vsz-start_vsz, end_rss-start_rss, adjust or 0)
    print 'Total time: %03.4f sec' % (end - start)
    print
    return end - start

DESCRIPTION = """\
This runs performance tests for HTML parsing and serialization.
Generally there are three kinds of tests:

* Test parsing
* Test serialization
* Test memory use

There are a variety of libraries and library combinations supported.
Some are parsers, some document models, in different supported
combinations.  You may have to install external modules to make these
all work (e.g., html5lib, BeautifulSoup, ElementTree, cElementTree,
Genshi, lxml, FormEncode).
"""

def main(args=None):
    if args is None:
        args = sys.argv[1:]
    parser = optparse.OptionParser(
        usage="%%prog [options]\n\n%s" % DESCRIPTION)
    parser.add_option(
        '--type', '-t',
        action='append',
        dest='types',
        default=None,
        metavar='TYPE',
        help='Test this type of parser (from: %s).  Use * for all parsers' % ', '.join(sorted(type_map.keys())))
    parser.add_option(
        '--no-gc',
        action='store_true',
        dest='disable_gc',
        help='Disable gc during run')
    parser.add_option(
        '--keep-docs',
        action='store_true',
        dest='keep_docs',
        help='Keep the documents after they are parsed (instead of letting them be collected), then show memory use of the documents (requires a Posix/Linux system)')
    parser.add_option(
        '--keep-docs-subprocess',
        action='store_true',
        dest='keep_docs_subprocess',
        help='Run with --keep-docs in a subprocess, accumulating the output')
    parser.add_option(
        '--serialize',
        action='store_true',
        dest='serialize',
        help='Serialize after parsing')
    parser.add_option(
        '--sample-data',
        dest='sample_data',
        default=sample_data,
        metavar='DIR',
        help='Directory containing sample HTML files (default: %s)' % sample_data)
    options, args = parser.parse_args(args)
    if not options.types:
        print 'No --type given'
        parser.print_help()
        sys.exit(2)
    if '*' in options.types:
        options.types.remove('*')
        for key in sorted(type_map.keys()):
            if key not in options.types:
                options.types.append(key)
    for type in options.types:
        if type not in type_map:
            print 'No type %s' % type
            sys.exit(2)
        t = type_map[type]()
    results = {}
    if options.keep_docs_subprocess:
        label = '%(name)s (%(number).1f Mb)'
        for type_name in options.types:
            results[type_name] = run_subprocess_keep_docs(type_name)
    else:
        label = '%(name)s (%(number).1f sec)'
        for type_name in options.types:
            type = type_map[type_name]()
            results[type_name] = test_type(
                type, disable_gc=options.disable_gc,
                keep_docs=options.keep_docs,
                serialize=options.serialize,
                sample_data=options.sample_data)
    if len(results) > 1:
        print
        print 'Summary:'
        reference_type = options.types[0]
        reference = results[reference_type]
        for type_name in options.types:
            print '%s%s: % 04.4f sec (%4i%% of %s)' % (
                type_name, (15-len(type_name)) * ' ',
                results[type_name],
                100.0*results[type_name] / reference,
                reference_type)
        print make_chart_url(
            [(type_map[type_name].description, results[type_name]) for type_name in options.types],
            name_format=label)

def run_subprocess_keep_docs(type_name):
    print 'Running', ' '.join([sys.executable, sys.argv[0], '-t', type_name, '--keep-docs'])
    proc = subprocess.Popen([sys.executable, sys.argv[0], '-t', type_name, '--keep-docs'],
                            stdout=subprocess.PIPE)
    output, stderr = proc.communicate()
    print output
    match = re.search(r'(\d+)\s+/\s+(\d+)\s+[(]unused:\s+(\d+)[)]', output)
    if not match:
        print 'Output did not match!'
        return 0
    return int(match.group(2))/1000.0

def make_chart_url(data, size_x=400, size_y=None, graph_type='bhs', name_format='%(name)s'):
    url = 'http://chart.apis.google.com/chart?'
    params = {}
    if size_y is None:
        size_y = len(data)*30
    params['chs'] = '%sx%s' % (size_x, size_y)
    numbers = [number for name, number in data]
    params['chd'] = 'e:' + ''.join(list(encode_numbers(numbers)))
    names = [name_format % dict(name=name, number=number) for name, number in data]
    params['chxl'] = '0:|%s|' % '|'.join(reversed(names))
    params['chxt'] = 'y'
    params['cht'] = graph_type
    return url + urllib.urlencode(params)

digits = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-.'

def encode_numbers(numbers, lowest=0):
    """
    Encodes numbers over the range of 0-4095
    """
    if lowest is None:
        lowest = min(numbers)
    highest = max(numbers)
    range = highest-lowest
    for number in numbers:
        adjusted = int((number - lowest) * 4095 / range)
        assert adjusted >= 0 and adjusted <= 4095, 'Out of range: %r' % adjusted
        yield digits[adjusted / 64] + digits[adjusted % 64]

if __name__ == '__main__':
    main()
    
