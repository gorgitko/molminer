# MolMiner
MolMiner is a library and command-line interface for extracting compounds from scientific literature written in Python (currently supporting only Python 3). Actually it's a wrapper around several open-source tools for chemical information retrieval, namely [ChemSpot][1], [OSRA][2] and [OPSIN][3].
# Overview
MolMiner is able to extract chemical entities from various sources of scientific literature including PDF and scanned images. It extracts entities both from text and 2D structures. Text entities are assigned to one of classes:
"SYSTEMATIC", "IDENTIFIER", "FORMULA", "TRIVIAL", "ABBREVIATION", "FAMILY", "MULTIPLE". IUPAC names can be converted to computer-readable format like SMILES or InChI. 2D stuctures are recognised in document and also converted to computer-readable format. Entities successfully converted to computer-readable format are standardized using [MolVS](https://github.com/mcs07/MolVS) library. Entities are also annotated in PubChem and ChemSpider databases using [PubChemPy](https://github.com/mcs07/PubChemPy) and [ChemSpiPy](https://github.com/mcs07/ChemSpiPy).

[1]: https://www.informatik.hu-berlin.de/de/forschung/gebiete/wbi/resources/chemspot/chemspot
[2]: https://sourceforge.net/p/osra/wiki/Home/
[3]: https://bitbucket.org/dan2097/opsin
