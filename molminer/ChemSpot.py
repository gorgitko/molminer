from .AbstractLinker import AbstractLinker
from .utils import common_subprocess, get_input_file_type, get_text, dict_to_csv
from .normalize import Normalizer
from .OPSIN import OPSIN

from rdkit.Chem import MolFromSmiles, MolToInchi, InchiToInchiKey

from pubchempy import get_compounds, BadRequestError, NotFoundError, PubChemHTTPError, ResponseParseError, ServerError, TimeoutError, PubChemPyError
from chemspipy import ChemSpider

from collections import ChainMap, OrderedDict
import logging
from tempfile import NamedTemporaryFile
import os
import re
import bisect
from time import sleep


logging.basicConfig(format="[%(levelname)s - %(filename)s:%(funcName)s:%(lineno)s] %(message)s")
verbosity_levels = {
    0: 100,
    1: logging.WARNING,
    2: logging.INFO
}

CHEMSPOT_VERSION = "2.0"


class ChemSpot(AbstractLinker):
    """
    Represents the ChemSpot software and acts as a linker between Python and command-line interface of ChemSpot.
    ChemSpot version: 2.0

    ChemSpot is a software for chemical Named Entity Recognition.
    It assigns to each chemical entity one of this classes:
    "SYSTEMATIC", "IDENTIFIER", "FORMULA", "TRIVIAL", "ABBREVIATION", "FAMILY", "MULTIPLE"
    More information here: https://www.informatik.hu-berlin.de/de/forschung/gebiete/wbi/resources/chemspot/chemspot

    ChemSpot is very memory-consuming so dictionary and ID lookup is disabled by default. Only CRF, OpenNLP sentence and
    multiclass models will be used by default.
    Maximum memory used by Java process is set to 8 GB by default. It is strongly recommended to use swap file on SSD disk when
    available memory is under 8 GB (see https://www.digitalocean.com/community/tutorials/how-to-add-swap-space-on-ubuntu-16-04 for more details).

    To show the meaning of options:
        chemspot = ChemSpot()
        print(chemspot.help())  # this will show the output of "$ chemspot -h"
        print(chemspot._OPTIONS_REAL)  # this will show the mapping between ChemSpot class and real ChemSpot parameters

    Attributes
    ----------
    _OPTIONS_REAL : dict
        Internal dict which maps the passed options to real ChemSpot command-line arguments. Static attribute.
    options : dict
        Get or set options.
    options_internal : dict
        Return dict with options having internal names.
    path_to_binary : str
        Path to ChemSpot binary.

    Methods
    -------
    process
        Process the input file with ChemSpot.
    help
        Return ChemSpot help message.
    """

    _OPTIONS_REAL = {
        "path_to_crf": ("-m", "{}"),
        "path_to_nlp": ("-s", "{}"),
        "path_to_dict": ("-d", "{}"),
        "path_to_ids": ("-i", "{}"),
        "path_to_multiclass": ("-M", "{}"),
        #"n_threads": ("-T", "{}"),
        "iob_format": ("-I", "")
    }

    # matches ion and charge e.g. from "Cu(2+)"
    RE_ION = re.compile(r"^\s*(?P<ion>[A-Z][a-z]?)\s*\((?P<charge>-?\+?i+\+?-?|-?\+?I+\+?-?|\d+\+|\d+-|\+\d+|-\d+|\++|-+)\)\s*$")
    # matches charge digit or its signs
    RE_CHARGE = re.compile(r"(?P<roman>i+|I+)|(?P<digit>\d+)|(?P<signs>^\++|-+$)")

    logger = logging.getLogger("chemspot")

    def __init__(self,
                 path_to_binary: str = "chemspot",
                 path_to_crf: str = "",
                 path_to_nlp: str = "",
                 path_to_dict: str = "",
                 path_to_ids: str = "",
                 path_to_multiclass: str = "multiclass.bin",
                 tessdata_path: str = "",
                 #n_threads: int = 0,
                 max_memory: int = 8,
                 verbosity: int = 1):
        """
        Parameters
        ----------
        path_to_binary
        path_to_crf : str
            Path to a CRF model file (internal default model file will be used if not provided).
        path_to_nlp : str
            Path to a OpenNLP sentence model file (internal default model file will be used if not provided).
        path_to_dict : str
            Path to a zipped set of brics dictionary automata. Disabled by default, set to 'dict.zip' to use default
            dictionary.
        path_to_ids : str
            Path to a zipped tab-separated text file representing a map of terms to ids. Disabled by default,
            set to `ids.zip` to use default IDs.
        path_to_multiclass : str
            Path to a multi-class model file. Enabled by default.
        tessdata_path : str
            Path to directory with Tesseract language data. If empty, the TESSDATA_PREFIX environment variable will be used.
        max_memory : int
            Maximum memory used by Java process.
        verbosity : int
            This class's verbosity. Values: 0, 1, 2
        """

        if verbosity > 2:
            verbosity = 2
        elif verbosity not in verbosity_levels:
            verbosity = 1
        self.logger.setLevel(verbosity_levels[verbosity])
        self.verbosity = verbosity

        self.path_to_binary = path_to_binary

        if not path_to_dict:
            path_to_dict = "\"''\""
        elif path_to_dict == "dict.zip" and "CHEMSPOT_DATA_PATH" in os.environ:
            path_to_dict = "{}/{}".format(os.environ["CHEMSPOT_DATA_PATH"], "dict.zip")

        if not path_to_ids:
            path_to_ids = "\"''\""
        elif path_to_ids == "ids.zip" and "CHEMSPOT_DATA_PATH" in os.environ:
            path_to_ids = "{}/{}".format(os.environ["CHEMSPOT_DATA_PATH"], "ids.zip")

        if path_to_multiclass == "multiclass.bin" and "CHEMSPOT_DATA_PATH" in os.environ:
            path_to_multiclass = "{}/{}".format(os.environ["CHEMSPOT_DATA_PATH"], "multiclass.bin")
        elif not path_to_multiclass:
            path_to_multiclass = "\"''\""

        if tessdata_path:
            os.environ["TESSDATA_PREFIX"] = tessdata_path

        self.re_ion = self.RE_ION
        self.re_charge = self.RE_CHARGE

        _, self.options, self.options_internal = self.build_commands(locals(), self._OPTIONS_REAL, path_to_binary)
        self.options_internal["max_memory"] = max_memory

    def set_options(self, options: dict):
        """
        Sets the options passed in dict. Keys are the same as optional parameters in ChemSpot constructor (__init__()).

        Parameters
        ----------
        options
            Dict of new options.
        """

        _, self.options, self.options_internal = self.build_commands(options, self._OPTIONS_REAL, self.path_to_binary)

    @staticmethod
    def version(self) -> str:
        """
        Returns
        -------
        str
            ChemSpot version.
        """

        return CHEMSPOT_VERSION

    def help(self) -> str:
        """
        Returns
        -------
        str
            ChemSpot help message.
        """

        stdout, stderr, _ = common_subprocess([self.path_to_binary, "1"])

        if stderr:
            return stderr
        else:
            return stdout

    def process(self,
                input_text: str = "",
                input_file: str = "",
                output_file: str = "",
                output_file_sdf: str = "",
                sdf_append: bool = False,
                input_type: str = "",
                lang: str = "eng",
                paged_text: bool = False,
                format_output: bool = True,
                opsin_types: list = None,
                standardize_mols: bool = True,
                convert_ions: bool = True,
                write_header: bool = True,
                iob_format: bool = False,
                dry_run: bool = False,
                csv_delimiter: str = ";",
                normalize_text: bool = True,
                #normalize_ent: bool = True,
                remove_duplicates: bool = False,
                annotate: bool = True,
                annotation_sleep: int = 2,
                chemspider_token: str = "") -> OrderedDict:
        """
        Process the input file with ChemSpot.

        Parameters
        ----------
        input_text : str
            String to be processed by ChemSpot.
        input_file : str
            Path to file to be processed by ChemSpot.
        output_file : str
            File to write output in.
        output_file_sdf : str
            File to write SDF output in. SDF is from OPSIN converted entities.
        sdf_append : bool
            If True, append new molecules to existing SDF file or create new one if doesn't exist. SDF is from OPSIN converted entities.
        input_type : str
            When empty, input (MIME) type will be determined from magic bytes.
            Or you can specify "pdf", "pdf_scan", "image" or "text" and magic bytes check will be skipped.
        lang : str
            Language which will Tesseract use for OCR. Available languages: https://github.com/tesseract-ocr/tessdata
            Multiple languages can be specified with "+" character, i.e. "eng+bul+fra".
        paged_text : bool
            If True and `input_type` is "text" or `input_text` is provided, try to assign pages to chemical entities.
            ASCII control character 12 (Form Feed, "\f") is expected between pages.
        format_output : bool
            If True, the value of "content" key of returned dict will be list of OrderedDicts.
            If True and `output_file` is set, the CSV file will be written.
            If False, the value of "content" key of returned dict will be None.
        opsin_types : list
            List of ChemSpot entity types. Entities of types in this list will be converted with OPSIN. If you don't want
            to convert entities, pass empty list.
            OPSIN is designed to convert IUPAC names to linear notation (SMILES etc.) so default value of `opsin_types`
            is ["SYSTEMATIC"] (these should be only IUPAC names).
            ChemSpot entity types: "SYSTEMATIC", "IDENTIFIER", "FORMULA", "TRIVIAL", "ABBREVIATION", "FAMILY", "MULTIPLE"
        standardize_mols : bool
            If True, use molvs (https://github.com/mcs07/MolVS) to standardize molecules converted by OPSIN.
        convert_ions : bool
            If True, try to convert ion entities (e.g. "Ni(II)") to SMILES. Entities matching ion regex won't be converted
            with OPSIN.
        write_header : bool
            If True and if `output_file` is set and `output_format` is True, write a CSV write_header:
                "smiles", "bond_length", "resolution", "confidence", "learn", "page", "coordinates"
        iob_format : bool
            If True, output will be in IOB format.
        dry_run : bool
            If True, only return list of commands to be called by subprocess.
        csv_delimiter : str
            Delimiter for output CSV file.
        normalize_text : bool
            If True, normalize text before performing NER. It is strongly recommended to do so, because without normalization
            can ChemSpot produce unpredictable results which cannot be parsed.
        NOT IMPLEMENTED | normalize_ent : bool
            If True, normalize the found chemical entities (first letter to lowercase etc.).
        remove_duplicates : bool
            If True, remove duplicated chemical entities. Note that some entities-compounds can have different names, but
            same notation (SMILES, InChI etc.). This will only remove entities with same names.
            Not applicable for IOB format.
        annotate : bool
            If True, try to annotate entities in PubChem and ChemSpider. Compound IDs will be assigned by searching with
            each identifier, separately for entity name, SMILES etc.
            If entity has InChI key yet, prefer it in searching.
            If "*" is present in SMILES, skip annotation.
            If textual entity has single result in DB when searched by name, fill in missing identifiers (SMILES etc.).
        annotation_sleep: int
            How many seconds to sleep between annotation of each entity. It's for preventing overloading of databases.
        chemspider_token : str
            Your personal token for accessing the ChemSpider API (needed for annotation). Make account there to obtain it.

        Returns
        -------
        dict
            Keys:
                stdout: str ... standard output from ChemSpot
                stderr: str ... standard error output from ChemSpot
                exit_code: int ... exit code from ChemSpot
                content:
                    list of OrderedDicts ... when `format_output` is True
                    None ... when `format_output` is False
                normalized_text : str
        """

        if opsin_types is None:
            opsin_types = ["SYSTEMATIC"]

        if input_text and input_file:
            input_file = ""
            self.logger.warning("Both 'input_text' and 'input_file' are set, but 'input_text' will be prefered.")
        elif not input_text and not input_file:
            raise ValueError("One of 'input_text' or 'input_file' must be set.")

        if not input_type and not input_text:
            possible_input_types = ["pdf", "image", "text"]
            input_type = get_input_file_type(input_file)
            if input_type not in possible_input_types:
                raise ValueError("Input file type ({}) is not one of {}".format(input_type, possible_input_types))
        elif input_type and not input_text:
            possible_input_types = ["pdf", "pdf_scan", "image", "text"]
            if input_type not in possible_input_types:
                raise ValueError("Unknown 'input_type'. Possible 'input_type' values are {}".format(possible_input_types))

        if input_type in ["pdf", "pdf_scan", "image"]:
            input_text, _ = get_text(input_file, input_type, lang=lang, tessdata_prefix=os.environ["TESSDATA_PREFIX"])
            input_file = ""

        if annotate and not chemspider_token:
            self.logger.warning("Cannot perform annotation in ChemSpider: 'chemspider_token' is empty.")

        options = ChainMap({k: v for k, v in {"iob_format": iob_format}.items() if v},
                           self.options_internal)
        output_file_temp = None

        commands, _, _ = self.build_commands(options, self._OPTIONS_REAL, self.path_to_binary)
        commands.insert(1, str(self.options_internal["max_memory"]))
        commands.append("-t")

        if normalize_text:
            normalizer = Normalizer(strip=True, collapse=True, hyphens=True, quotes=True, slashes=True, tildes=True, ellipsis=True)

            if input_file:
                with open(input_file, mode="r") as f:
                    input_text = f.read()

            input_text = normalizer(input_text)

            if not input_text:
                raise UserWarning("'input_text' is empty after normalization.")

            input_text = self.normalize_text(text=input_text)
            input_file_normalized = NamedTemporaryFile(mode="w", encoding="utf-8")
            input_file_normalized.write(input_text)
            input_file_normalized.flush()
            input_file = input_file_normalized.name
        else:
            if input_text:
                input_file_temp = NamedTemporaryFile(mode="w", encoding="utf-8")
                input_file_temp.write(input_text)
                input_file_temp.flush()
                input_file = input_file_temp.name

        commands.append(os.path.abspath(input_file))
        commands.append("-o")
        if format_output:
            output_file_temp = NamedTemporaryFile(mode="w", encoding="utf-8")
            commands.append(os.path.abspath(output_file_temp.name))
        else:
            commands.append(os.path.abspath(output_file))

        if dry_run:
            return " ".join(commands)

        stdout, stderr, exit_code = common_subprocess(commands)

        if "OutOfMemoryError" in stderr:
            raise RuntimeError("ChemSpot memory error: {}".format(stderr))

        to_return = {"stdout": stdout, "stderr": stderr, "exit_code": exit_code, "content": None,
                     "normalized_text": input_text if normalize_text else None}

        if normalize_text:
            to_return["normalized_text"] = input_text

        if not format_output:
            return to_return
        elif format_output:
            with open(output_file_temp.name, mode="r", encoding="utf-8") as f:
                output_chs = f.read()

            entities = self.parse_chemspot_iob(text=output_chs) if iob_format else self.parse_chemspot(text=output_chs)
            to_return["content"] = entities

            if remove_duplicates and not iob_format:
                seen = set()
                seen_add = seen.add
                to_return["content"] = [x for x in to_return["content"] if not (x["entity"] in seen or seen_add(x["entity"]))]

            if input_type in ["pdf", "pdf_scan"] or paged_text:
                page_ends = []
                for i, page in enumerate(input_text.split("\f")):
                    if page.strip():
                        try:
                            page_ends.append(page_ends[-1] + len(page) - 1)
                        except IndexError:
                            page_ends.append(len(page) - 1)

            if opsin_types:
                if convert_ions:
                    to_convert = [x["entity"] for x in to_return["content"] if x["type"] in opsin_types and not self.re_ion.match(x["entity"])]
                else:
                    to_convert = [x["entity"] for x in to_return["content"] if x["type"] in opsin_types]

                if to_convert:
                    opsin = OPSIN(verbosity=self.verbosity)
                    opsin_converted = opsin.process(input=to_convert, output_formats=["smiles", "inchi", "inchikey"],
                                                    standardize_mols=standardize_mols, output_file_sdf=output_file_sdf,
                                                    sdf_append=sdf_append)
                    opsin_converted = iter(opsin_converted["content"])
                else:
                    self.logger.info("Nothing to convert with OPSIN.")

            if annotate:
                chemspider = ChemSpider(chemspider_token)

            for i, ent in enumerate(to_return["content"]):
                if input_type in ["pdf", "pdf_scan"] or paged_text:
                    ent["page"] = str(bisect.bisect_left(page_ends, int(ent["start"])) + 1)

                if convert_ions:
                    match_ion = self.re_ion.match(ent["entity"])
                    if match_ion:
                        match_ion = match_ion.groupdict()
                        match_charge = self.re_charge.search(match_ion["charge"])
                        if match_charge:
                            match_charge = match_charge.groupdict()
                            if match_charge["roman"]:
                                smiles = "[{}+{}]".format(match_ion["ion"], len(match_charge["roman"]))
                            elif match_charge["digit"]:
                                if "+" in match_ion["charge"]:
                                    smiles = "[{}+{}]".format(match_ion["ion"], match_charge["digit"])
                                elif "-" in match_ion["charge"]:
                                    smiles = "[{}-{}]".format(match_ion["ion"], match_charge["digit"])
                            elif match_charge["signs"]:
                                smiles = "[{}{}{}]".format(match_ion["ion"], match_charge["signs"][0],
                                                           len(match_charge["signs"]))

                            mol = MolFromSmiles(smiles)
                            if mol:
                                inchi = MolToInchi(mol)
                                if inchi:
                                    ent.update(OrderedDict(
                                        [("smiles", smiles), ("inchi", inchi), ("inchikey", InchiToInchiKey(inchi))]))
                                else:
                                    ent.update(OrderedDict([("smiles", smiles), ("inchi", ""), ("inchikey", "")]))
                            else:
                                ent.update(OrderedDict([("smiles", ""), ("inchi", ""), ("inchikey", "")]))
                    else:
                        ent.update(OrderedDict([("smiles", ""), ("inchi", ""), ("inchikey", "")]))

                if opsin_types and to_convert:
                    if ent["entity"] in to_convert:
                        ent_opsin = next(opsin_converted)
                        ent.update(OrderedDict([("smiles", ent_opsin["smiles"]), ("inchi", ent_opsin["inchi"]),
                                                ("inchikey", ent_opsin["inchikey"]), ("opsin_error", ent_opsin["error"])]))
                    elif convert_ions and self.re_ion.match(ent["entity"]):
                        ent.update(OrderedDict([("opsin_error", "")]))
                    elif (convert_ions and not self.re_ion.match(ent["entity"])) or (not convert_ions and ent["entity"] not in to_convert):
                        ent.update(OrderedDict([("smiles", ""), ("inchi", ""), ("inchikey", ""), ("opsin_error", "")]))

                # TODO: this should be simplified...looks like garbage code
                if annotate:
                    self.logger.info("Annotating entity {}/{}...".format(i + 1, len(to_return["content"])))
                    ent.update(OrderedDict([("pch_cids_by_inchikey", ""), ("chs_cids_by_inchikey", ""),
                                            ("pch_cids_by_name", ""), ("chs_cids_by_name", ""),
                                            ("pch_cids_by_smiles", ""), ("chs_cids_by_smiles", ""),
                                            ("pch_cids_by_inchi", ""), ("chs_cids_by_inchi", ""),
                                            ("pch_cids_by_formula", ""),
                                            ("pch_iupac_name", ""), ("chs_common_name", ""),
                                            ("pch_synonyms", "")]))

                    # do "double-annotation": some entities can be found in only one DB, updated and then searched in second DB
                    found_in_pch = False
                    found_in_chs = False
                    for _ in range(2):
                        results = []

                        # prefer InChI key
                        if "inchikey" in ent and ent["inchikey"]:
                            try:
                                results = get_compounds(ent["inchikey"], "inchikey")
                                if results:
                                    if len(results) == 1:
                                        result = results[0]
                                        synonyms = result.synonyms
                                        if synonyms:
                                            ent["pch_synonyms"] = "\"{}\"".format("\",\"".join(synonyms))
                                        ent["pch_iupac_name"] = result.iupac_name
                                        if not found_in_chs:
                                            ent["smiles"] = result.canonical_smiles or ent["smiles"]
                                            ent["inchi"] = result.inchi or ent["inchi"]
                                            ent["inchikey"] = result.inchikey or ent["inchikey"]
                                    ent["pch_cids_by_inchikey"] = "\"{}\"".format(",".join([str(c.cid) for c in results]))
                            except (BadRequestError, NotFoundError, PubChemHTTPError, ResponseParseError, ServerError, TimeoutError, PubChemPyError):
                                pass

                            results = chemspider.search(ent["inchikey"])
                            if results:
                                if len(results) == 1:
                                    result = results[0]
                                    ent["chs_common_name"] = result.common_name
                                    if not found_in_pch:
                                        ent["smiles"] = result.smiles or ent["smiles"]
                                        ent["inchi"] = result.stdinchi or ent["inchi"]
                                        ent["inchikey"] = result.stdinchikey or ent["inchikey"]
                                ent["chs_cids_by_inchikey"] = "\"{}\"".format(",".join([str(c.csid) for c in results]))
                        else:
                            if (not found_in_pch and not found_in_chs) or (not found_in_pch and found_in_chs):
                                try:
                                    results = get_compounds(ent["entity"] or ent["abbreviation"], "name")
                                    if results:
                                        if len(results) == 1:
                                            found_in_pch = True
                                            result = results[0]
                                            synonyms = result.synonyms
                                            if synonyms:
                                                ent["pch_synonyms"] = "\"{}\"".format("\",\"".join(synonyms))
                                            # only update identifiers if they weren't found in second DB
                                            if not found_in_chs:
                                                ent["smiles"] = result.canonical_smiles or ent["smiles"]
                                                ent["inchi"] = result.inchi or ent["inchi"]
                                                ent["inchikey"] = result.inchikey or ent["inchikey"]
                                            ent["pch_iupac_name"] = result.iupac_name
                                        ent["pch_cids_by_name"] = "\"{}\"".format(",".join([str(c.cid) for c in results]))
                                except (BadRequestError, NotFoundError, PubChemHTTPError, ResponseParseError, ServerError, TimeoutError, PubChemPyError):
                                    pass

                            if (not found_in_pch and not found_in_chs) or (found_in_pch and not found_in_chs):
                                results = chemspider.search(ent["entity"] or ent["abbreviation"])
                                if results:
                                    if len(results) == 1:
                                        found_in_chs = True
                                        result = results[0]
                                        if not found_in_pch:
                                            ent["smiles"] = result.smiles or ent["smiles"]
                                            ent["inchi"] = result.stdinchi or ent["inchi"]
                                            ent["inchikey"] = result.stdinchikey or ent["inchikey"]
                                        ent["chs_common_name"] = result.common_name
                                    ent["chs_cids_by_name"] = "\"{}\"".format(",".join([str(c.csid) for c in results]))

                            for search_field, col_pch, col_chs in [("smiles", "pch_cids_by_smiles", "chs_cids_by_smiles"),
                                                                   ("inchi", "pch_cids_by_inchi", "chs_cids_by_inchi"),
                                                                   ("formula", "pch_cids_by_formula", "")]:
                                results_pch = []
                                results_chs = []

                                if search_field == "smiles" and "smiles" in ent and ent["smiles"] and "*" not in ent["smiles"]:
                                    if (not found_in_pch and not found_in_chs) or (not found_in_pch and found_in_chs):
                                        try:
                                            results_pch = get_compounds(ent["smiles"], "smiles")
                                        except (BadRequestError, NotFoundError, PubChemHTTPError, ResponseParseError, ServerError, TimeoutError, PubChemPyError):
                                            pass
                                    if (not found_in_pch and not found_in_chs) or (found_in_pch and not found_in_chs):
                                        results_chs = chemspider.search(ent["smiles"])
                                elif search_field == "inchi" and "inchi" in ent and ent["inchi"]:
                                    if (not found_in_pch and not found_in_chs) or (not found_in_pch and found_in_chs):
                                        try:
                                            results_pch = get_compounds(ent["inchi"], "inchi")
                                        except (BadRequestError, NotFoundError, PubChemHTTPError, ResponseParseError, ServerError, TimeoutError, PubChemPyError):
                                            pass
                                    if (not found_in_pch and not found_in_chs) or (found_in_pch and not found_in_chs):
                                        results_chs = chemspider.search(ent["inchi"])
                                elif search_field == "formula":
                                    if (not found_in_pch and not found_in_chs) or (not found_in_pch and found_in_chs):
                                        try:
                                            results_pch = get_compounds(ent["entity"], "formula")
                                        except (BadRequestError, NotFoundError, PubChemHTTPError, ResponseParseError, ServerError, TimeoutError, PubChemPyError):
                                            pass
                                    # ChemSpider doesn't have search field for 'formula'

                                if results_pch:
                                    ent[col_pch] = "\"{}\"".format(",".join([str(c.cid) for c in results_pch]))
                                if results_chs:
                                    ent[col_chs] = "\"{}\"".format(",".join([str(c.csid) for c in results_chs]))

                                sleep(0.5)

                        sleep(annotation_sleep)

                        if not found_in_pch and not found_in_chs:
                            break

            if output_file:
                dict_to_csv(to_return["content"], output_file=output_file, csv_delimiter=csv_delimiter, write_header=write_header)

        return to_return

    @staticmethod
    def normalize_text(input_file_path: str = "", text: str = "", output_file_path: str = "",
                       encoding: str = "utf-8") -> str:
        """
        Normalize the text. Operations:
            - remove numbers of entities which points somewhere in the text, e.g. "N-octyl- (2b)" -> "N-octyl-"
            - replace "-\n" with ""

        Parameters
        ----------
        input_file_path : str
        text : str
        output_file_path : str
        encoding : str

        Returns
        -------
        str
            Normalized text.

        Notes
        -----
        One of `input_file_path` or `text` parameters must be set.
        """

        if not input_file_path and not text:
            raise ValueError("One of 'input_file_path' or 'text' must be set.")

        if input_file_path:
            with open(input_file_path, mode="r", encoding=encoding) as file:
                text = file.read()

        text = re.sub(re.compile(r"\(?\d+[a-zA-Z]\)?,?"), "", text)
        text = text.replace("-\n", "")

        if output_file_path:
            with open(output_file_path, mode="w", encoding=encoding) as file:
                file.write(text)

        return text

    @staticmethod
    def parse_chemspot(file_path: str = "", text: str = "", encoding: str = "utf-8") -> list:
        """
        Parse the output from ChemSpot.

        Parameters
        ----------
        file_path : str
            Path to file.
        text : str
            Text to normalize.
        encoding : str
            File encoding.

        Returns
        -------
        list
            List of lists. Each sublist is one row from input file and contains:
            start position, end position, name of entity, type
            Type means a type of detected entity, e.g. SYSTEMATIC, FAMILY etc.
        """

        if file_path:
            with open(file_path, mode="r", encoding=encoding) as f:
                text = f.read()

        rows = [row.strip().split("\t") for row in text.strip().split("\n") if row]

        # Sometimes newline causes ChemSpot to have bad output like
        #   5355	5396	3-(cyclohexylamino)-1-propanesulfonic \n
        #   acid	SYSTEMATIC
        # This fixes it.

        rows_new = []
        rows_enumerator = enumerate(rows)

        for i, row in rows_enumerator:
            if row[3] == "ABBREVIATION":
                abbreviation = row[2]
            else:
                abbreviation = ""

            if len(row) == 4:
                rows_new.append(OrderedDict([("start", row[0]), ("end", row[1]), ("page", 1), ("abbreviation", abbreviation),
                                             ("entity", row[2]), ("type", row[3])]))
            elif len(row) == 5:
                rows_new.append(OrderedDict([("start", row[0]), ("end", row[1]), ("page", 1), ("abbreviation", abbreviation),
                                             ("entity", row[4]), ("type", row[3])]))
            else:
                next_row = next(rows_enumerator)[1]
                rows_new.append(OrderedDict([("start", row[0]), ("end", row[1]), ("page", 1), ("abbreviation", abbreviation),
                                             ("entity", row[2] + " " + next_row[0]), ("type", next_row[1])]))
        return rows_new

    @staticmethod
    def parse_chemspot_iob(file_path: str = "", text: str = "", encoding: str = "utf-8") -> list:
        if file_path:
            with open(file_path, mode="r", encoding=encoding) as f:
                text = f.readlines()
        elif text:
            text = [x.strip() for x in text.split("\n")]

        text = iter(text)
        rows = []

        next(text)  # skip first row containing "###"
        for row in text:
            row = row.strip().split()
            if len(row) == 4:
                rows.append(OrderedDict([("string", row[0]), ("start", row[1]), ("end", row[2]), ("page", "1"), ("type", row[3])]))
            elif len(row) == 3:
                rows.append(OrderedDict([("string", ""), ("start", row[0]), ("end", row[1]), ("page", "1"), ("type", row[2])]))
        return rows
