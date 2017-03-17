# MolMiner
MolMiner is a library and command-line interface for extracting compounds from scientific literature written in Python (currently supporting only Python 3). Actually it's a wrapper around several open-source tools for chemical information retrieval, namely [ChemSpot][1], [OSRA][2] and [OPSIN][3].
# Overview
MolMiner is able to extract chemical entities from various sources of scientific literature including PDF and scanned images. It extracts entities both from text and 2D structures. Text is normalized using part of code from [ChemDataExtractor](https://github.com/mcs07/ChemDataExtractor/blob/master/chemdataextractor/text/normalize.py). Text entities are assigned by [ChemSpot][1] to one of classes: "SYSTEMATIC", "IDENTIFIER", "FORMULA", "TRIVIAL", "ABBREVIATION", "FAMILY", "MULTIPLE". IUPAC names can be converted to computer-readable format like SMILES or InChI with [OPSIN][3]. 2D stuctures are recognised in document and converted to computer-readable format with [OSRA][2]. Entities successfully converted to computer-readable format are standardized using [MolVS](https://github.com/mcs07/MolVS) library. Entities are also annotated in PubChem and ChemSpider databases using [PubChemPy](https://github.com/mcs07/PubChemPy) and [ChemSpiPy](https://github.com/mcs07/ChemSpiPy).

For processing of PDF files is used [GraphicsMagick][4] and for OCR [Tesseract][4].
# Installation
MolMiner self is written in Python, but it uses several binaries and some of them have complicated compilation dependencies. So the easiest way is to install MolMiner including dependencies as a [conda][6] package hosted on [Anaconda Cloud](https://anaconda.org/).

## Conda package (currently only for linux64)
[Conda][6] is a package, dependency and environment management for any language including Python.

**TO BE DONE**

<!---
1. Download _conda_ from https://conda.io/miniconda.html
2. Create new environment: `$ conda create -n my_new_env python=3`
3. Activate environment: `$ source activate my_new_env`
4. Install MolMiner: `$ conda install -c lich molminer`
5. Use MolMiner: `$ molminer --help`
--->
## From source (linux64)
### Binaries
You need all these binaries for MolMiner. They should be installed so path to them is in `$PATH` environment variable (like `/usr/local/bin`).
- [OSRA][2]. This is probably the most complicated binary. Official information is [here](https://sourceforge.net/p/osra/wiki/Dependencies/) and [here](https://github.com/gorgitko/molminer/blob/master/docs/osra-readme.txt). My installation notes are [here](https://github.com/gorgitko/molminer/blob/master/docs/osra-installation.txt).
  - Compile GraphicsMagick with as many supported image formats as possible.
  - Use Tesseract version 4 and up.
  - [Patched version](https://sourceforge.net/projects/osra/files/openbabel-patched/) of OpenBabel is needed.
- [ChemSpot][1]. Just download

[1]: https://www.informatik.hu-berlin.de/de/forschung/gebiete/wbi/resources/chemspot/chemspot
[2]: https://sourceforge.net/p/osra/wiki/Home/
[3]: https://bitbucket.org/dan2097/opsin
[4]: http://www.graphicsmagick.org/
[5]: https://github.com/tesseract-ocr/tesseract
[6]: https://conda.io/docs/index.html
