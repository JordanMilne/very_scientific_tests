	$ python2 htmlperf.py -t lxml --no-gc --keep-docs
	[...]
	Increased VSZ/RSS:
	lxml           :  10180  /  10612   (unused:    0)
	Total time: 0.0176 sec



	$ python2 htmlperf.py -t lxml_sax --no-gc --keep-docs
	[...]	
	Increased VSZ/RSS:
	lxml_sax       :  10176  /  10560   (unused:    0)
	Total time: 0.0705 sec
