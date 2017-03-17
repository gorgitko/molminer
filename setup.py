import os
from setuptools import setup, find_packages


if os.path.exists('README.rst'):
    long_description = open('README.rst').read()
else:
    long_description = '''A toolkit for extracting chemical information from the scientific literature.'''

setup(
    name='MolMiner',
    version='1.0.0',
    author='Jiri Novotny',
    author_email='fg-42@seznam.cz',
    license='MIT',
    #url='https://github.com/mcs07/ChemDataExtractor',
    packages=find_packages(),
    description='Library and CLI for extraction of chemical compounds from scientific papers.',
    #long_description=long_description,
    keywords='text-mining mining chemistry cheminformatics nlp science scientific ocsr ner',
    zip_safe=False,
    entry_points={'console_scripts': ['molminer = molminer.cli:cli']},
    #tests_require=['pytest'],
    install_requires=['joblib', 'molvs', 'python-magic', 'click'],
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: MIT License',
        'Operating System :: Unix',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Topic :: Internet :: WWW/HTTP :: Indexing/Search',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Bio-Informatics',
        'Topic :: Scientific/Engineering :: Chemistry',
        'Topic :: Text Processing',
        'Topic :: Text Processing :: Linguistic',
    ],
)