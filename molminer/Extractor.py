from .OPSIN import OPSIN
from .OSRA import OSRA
from .ChemSpot import ChemSpot
from .utils import get_input_file_type, dict_to_csv, get_temp_images, get_text, write_empty_file

from joblib import Parallel, delayed

from collections import OrderedDict
import logging
#import multiprocessing as mp
import os


logging.basicConfig(format="[%(levelname)s - %(filename)s:%(funcName)s:%(lineno)s] %(message)s")
verbosity_levels = {
    0: 100,
    1: logging.WARNING,
    2: logging.INFO
}


class Extractor(object):
    """
    Combines the OSRA, ChemSpot and OPSIN to extract chemical entities from article. These include 2D structures converted
    to linear notation and compounds found in text. Entities are converted to linear notation (SMILES etc.) with OPSIN
    (defaultly only IUPAC ones).

    Methods
    -------
    process
    """

    opsin_default_options = {
        "allow_acids_without_acid": True,
        "detailed_failure_analysis": True,
        "allow_radicals": True,
        "allow_uninterpretable_stereo": True,
        "wildcard_radicals": False,
    }

    osra_default_options = {
        "size": "",
        "superatom_config_path": "",
        "spelling_config_path": "",
        "adaptive": False,
        "jaggy": False,
        "unpaper": 0,
        "gray_threshold": 0.0,
        "resolution": 0,
        "negate": False,
        "rotate": 0
     }

    chemspot_default_options = {
        "path_to_crf": "",
        "path_to_nlp": "",
        "path_to_dict": "''",
        "path_to_ids": "''",
        "path_to_multiclass": "multiclass.bin",
        #"n_threads": 0,
        "max_memory": 8
    }

    logger = logging.getLogger("opsin")

    def __init__(self,
                 opsin_options: dict = opsin_default_options,
                 osra_options: dict = osra_default_options,
                 chemspot_options: dict = chemspot_default_options,
                 tessdata_path: str = "",
                 verbosity: int = 1,
                 verbosity_classes: int = 1):
        """
        All supporting class options are kwargs in their __init__ methods.

        Parameters
        ----------
        opsin_options : dict
        osra_options : dict
        chemspot_options : dict
        tessdata_path : str
            Path to directory with Tesseract language data. If empty, the TESSDATA_PREFIX environment variable will be used.
        verbosity : int
            This class's verbosity. Values: 0, 1, 2
        verbosity_classes : int
            Verbosity of ChemSpot, OPSIN and OSRA classes. Values: 0, 1, 2
        """

        if tessdata_path:
            os.environ["TESSDATA_PREFIX"] = tessdata_path

        if verbosity > 2:
            verbosity = 2
        elif verbosity not in verbosity_levels:
            verbosity = 1
        self.logger.setLevel(verbosity_levels[verbosity])

        if verbosity_classes > 2:
            verbosity_classes = 2
        elif verbosity_classes not in verbosity_levels:
            verbosity_classes = 1

        osra_options["verbosity"] = verbosity_classes
        chemspot_options["verbosity"] = verbosity_classes
        opsin_options["verbosity"] = verbosity_classes

        self.osra = OSRA(**osra_options)
        self.chemspot = ChemSpot(**chemspot_options)
        self.opsin = OPSIN(**opsin_options)

    """
    def _parallel_job(self, worker, queue, input, **kwargs):
        if isinstance(worker, OSRA):
            result = worker.process(input, **kwargs)
            worker_name = "osra"
        elif isinstance(worker, ChemSpot):
            result = worker.process(input_text=input, **kwargs)
            worker_name = "chemspot"
        else:
            result = None
            worker_name = "unknown"

        queue.put({worker_name: result})

    def joblib_job(self, receiver, **kwargs):
        if receiver == "osra":
            self.logger.info("joblib: Extracting 2D structures with OSRA...")
            return {"osra": self.osra.process(**kwargs)}
        elif receiver == "chemspot":
            self.logger.info("joblib: Extracting chemical entities with ChemSpot...")
            return {"chemspot": self.chemspot.process(**kwargs)}
    """

    def process(self,
                input_file: str,
                output_file: str = "",
                output_file_sdf: str = "",
                sdf_append: bool = False,
                write_header: bool = True,
                separated_output: bool = False,
                input_type: str = "",
                lang: str = "eng",
                use_gm: bool = True,
                n_jobs: int = -1,
                opsin_types: list = None,
                convert_ions: bool = True,
                standardize_mols: bool = True,
                remove_entity_duplicates: bool = False,
                csv_delimiter: str = ";",
                annotate: bool = True,
                annotation_sleep: int = 2,
                chemspider_token: str = "") -> list:
        """
        Process the input file with OSRA and ChemSpot. IUPAC entities found by ChemSpot are converted by OPSIN to linear
        notation.

        Parameters
        ----------
        input_file : str
        output_file : str
            File to write output in.
        output_file_sdf : str
            File to write SDF output in. This will write SDF file separately from OSRA and OPSIN, with "-osra.sdf" and
            "-opsin.sdf" suffixes.
        sdf_append : bool
            If True, append new molecules to existing SDF file or create new one if doesn't exist.
        write_header : bool
            If True and if `output_file` is set and `output_format` is True, write a CSV write_header.
        separated_output : bool
            | If True, return OrderedDicts from each of OSRA, ChemSpot and OPSIN process methods.
            | If True and `output_file` is set, two separated CSV files will be written with suffixes ".ocsr", ".ner" and ".opsin".
        input_type : str
            | Type of input file. Values: "pdf", "pdf_scan", "image"
            | If "pdf", embedded text will be extracted by Poppler utils (pdftotext).
            | If "pdf_scan", PDF will be converted to images and text extracted by OCR (Tesseract).
            | If "image", text will be extracted by OCR (Tesseract).
            | If empty, input (MIME) type will be determined from magic bytes. Note that "pdf_scan" cannot be determined
              from magic bytes, because it looks like a normal PDF.
        lang : str
            | Language which will Tesseract use for OCR. Available languages: https://github.com/tesseract-ocr/tessdata
            | Multiple languages can be specified with "+" character, i.e. "eng+bul+fra".
        use_gm : bool
            | If True, use GraphicsMagick to convert PDF to images and then process each image with OSRA.
              OSRA itself can handle PDF files, but some additional information is then
              invalid and also some structures are wrongly recognised.
        n_jobs : int
            | Number of jobs for parallel processing with OSRA.
            | If -1 all CPUs are used.
            | If 1 is given, no parallel computing code is used at all, which is useful for debugging.
            | For n_jobs below -1, (n_cpus + 1 + n_jobs) are used. Thus for n_jobs = -2, all CPUs but one are used.
        opsin_types : list
            | List of ChemSpot entity types. Entities of types in this list will be converted with OPSIN.
            | OPSIN is designed to convert IUPAC names to linear notation (SMILES etc.) so default value of `opsin_types`
              is ["SYSTEMATIC"] (these should be only IUPAC names).
            | ChemSpot entity types: "SYSTEMATIC", "IDENTIFIER", "FORMULA", "TRIVIAL", "ABBREVIATION", "FAMILY", "MULTIPLE"
        convert_ions : bool
            If True, try to convert ion entities (e.g. "Ni(II)") to SMILES. Entities matching ion regex won't be converted
            with OPSIN.
        standardize_mols : bool
            If True, use molvs (https://github.com/mcs07/MolVS) to standardize molecules.
        remove_entity_duplicates : bool
            If True, remove duplicated chemical entities. Note that some entities-compounds can have different names, but
            same notation (SMILES, InChI etc.). This will only remove entities with same names.
        csv_delimiter : str
            Delimiter for output CSV file.
        annotate : bool
            | If True, try to annotate entities in PubChem and ChemSpider. Compound IDs will be assigned by searching with
              each identifier, separately for entity name, SMILES etc.
            | If entity has InChI key yet, prefer it in searching.
            | If "*" is present in SMILES, skip annotation.
            | If textual entity has single result in DB when searched by name, fill in missing identifiers (SMILES etc.).
        annotation_sleep: int
            How many seconds to sleep between annotation of each entity. It's for preventing overloading of databases.
        chemspider_token : str
            Your personal token for accessing the ChemSpider API (needed for annotation). Make account there to obtain it.

        Returns
        -------
        list of OrderedDicts
            Keys: "source", "type", "page", "abbreviation", "entity", "smiles", "inchi", "inchikey"
        OrderedDict, OrderedDict, OrderedDict
            From OSRA, ChemSpot and OPSIN if `separated_output` is True.
        """

        if not opsin_types:
            opsin_types = ["SYSTEMATIC"]

        if not input_type:
            input_type = get_input_file_type(input_file)
            possible_input_types = ["pdf", "image"]
            if input_type not in possible_input_types:
                raise ValueError("Input file type ({}) is not one of {}".format(input_type, possible_input_types))
        else:
            possible_input_types = ["pdf", "pdf_scan", "image"]
            if input_type not in possible_input_types:
                raise ValueError("Unknown 'input_type'. Possible 'input_type' values are {}".format(possible_input_types))

        output_file_sdf_osra = ""
        output_file_sdf_opsin = ""
        if output_file_sdf:
            output_file_sdf_osra = output_file_sdf + "-osra.sdf"
            output_file_sdf_opsin = output_file_sdf + "-opsin.sdf"

        output_file_ocsr = ""
        output_file_ner = ""
        output_file_opsin = ""

        if separated_output and output_file:
            output_file_ocsr = "{}.ocsr".format(output_file)
            output_file_ner = "{}.ner".format(output_file)
            output_file_opsin = "{}.opsin".format(output_file)
        elif separated_output and not output_file:
            separated_output = False
            self.logger.warning("Cannot write separated output: 'output_file' is not set.")

        self.logger.info("Extracting text..." + (" (Tesseract OCR)" if input_type == "pdf_scan" else ""))
        text, temp_images_dir = get_text(input_file, input_type, lang=lang)

        if input_type == "pdf_scan":
            self.logger.info("Converting PDF to temporary images...")
            temp_image_files = get_temp_images(temp_images_dir.name)

            self.logger.info("Parallely extracting 2D structures with OSRA...")
            ocsr_list = Parallel(n_jobs=n_jobs)(
                delayed(self.osra.process)(temp_image_file, use_gm=False, input_type="image", custom_page=page,
                                           output_formats=["smiles", "inchi", "inchikey"], osra_output_format="sdf",
                                           standardize_mols=standardize_mols, output_file_sdf=output_file_sdf_osra, sdf_append=sdf_append,
                                           annotate=annotate, chemspider_token=chemspider_token)
                                           for temp_image_file, page in temp_image_files)
            temp_images_dir.cleanup()
            ocsr = OrderedDict([("stdout", []), ("stderr", []), ("content", []), ("pages", [])])
            for x, (_, page) in zip(ocsr_list, temp_image_files):
                if x["stdout"][0]:
                    ocsr["stdout"].extend(x["stdout"])
                    ocsr["stderr"].extend(x["stderr"])
                    ocsr["content"].extend(x["content"])
                    ocsr["pages"].append(page)

            if separated_output and ocsr["content"]:
                self.logger.info("Writing separated output from OSRA...")
                dict_to_csv(ocsr["content"], output_file=output_file_ocsr, csv_delimiter=csv_delimiter, write_header=write_header)
            elif separated_output and not ocsr["content"]:
                write_empty_file(output_file, csv_delimiter=csv_delimiter, header=None, write_header=False)

            self.logger.info("Extracting chemical entities from text with ChemSpot...")
            ner = self.chemspot.process(input_text=text, remove_duplicates=remove_entity_duplicates,
                                        output_file=output_file_ner, paged_text=True, annotate=annotate,
                                        annotation_sleep=annotation_sleep, chemspider_token=chemspider_token,
                                        opsin_types=[], convert_ions=convert_ions, standardize_mols=standardize_mols)
        else:
            # Parallelization is not working for larger documents.
            # See http://stackoverflow.com/questions/21641887/python-multiprocessing-process-hangs-on-join-for-large-queue
            # And maybe it's because osra.process() is internally using joblib for converting PDF to images?
            """
            result_queue = mp.SimpleQueue()
            #result_queue = mp.Queue(maxsize=0)
            ocsr = mp.Process(target=self._parallel_job,
                              args=(self.osra, result_queue, input_file),
                              kwargs={"use_gm": use_gm, "output_formats": ["smiles", "inchi", "inchikey"],
                                      "osra_output_format": "smi", "standardize_mols": standardize_mols, "n_jobs": n_jobs,
                                      "output_file": output_file_ocsr, "input_type": input_type,
                                      "output_file_sdf": output_file_sdf_osra, "sdf_append": sdf_append})
            ner = mp.Process(target=self._parallel_job,
                             args=(self.chemspot, result_queue, text),
                             kwargs={"remove_duplicates": remove_entity_duplicates, "output_file": output_file_ner,
                                     "paged_text": True if input_type == "pdf" else False})

            self.logger.info("Starting parallelized extraction...")
            self.logger.info("Extracting 2D structures with OSRA...")
            ocsr.start()
            self.logger.info("Extracting chemical entities from text with ChemSpot...")
            ner.start()

            ocsr.join()
            ner.join()

            for _ in range(2):
                result = result_queue.get()
                if "osra" in result:
                    ocsr = result["osra"]
                elif "chemspot" in result:
                    ner = result["chemspot"]
            """

            self.logger.info("Extracting 2D structures with OSRA...")
            ocsr = self.osra.process(input_file=input_file, use_gm=use_gm, output_formats=["smiles", "inchi", "inchikey"],
                                     osra_output_format="smi", standardize_mols=standardize_mols, n_jobs=n_jobs,
                                     output_file=output_file_ocsr, input_type=input_type,
                                     output_file_sdf=output_file_sdf_osra, sdf_append=sdf_append,
                                     annotate=annotate, chemspider_token=chemspider_token)

            self.logger.info("Extracting chemical entities from text with ChemSpot...")
            ner = self.chemspot.process(input_text=text, remove_duplicates=remove_entity_duplicates,
                                        output_file=output_file_ner, paged_text=True if input_type == "pdf" else False,
                                        annotate=annotate, annotation_sleep=annotation_sleep, convert_ions=convert_ions,
                                        chemspider_token=chemspider_token, opsin_types=[], standardize_mols=standardize_mols)

        to_convert = [x["entity"] for x in ner["content"] if x["type"] in opsin_types]
        opsin_converted = []

        if to_convert:
            self.logger.info("Converting chemical entities with OPSIN...")
            opsin_converted = self.opsin.process(input=to_convert,
                                                 output_formats=["smiles", "inchi", "inchikey"], output_file=output_file_opsin,
                                                 output_file_sdf=output_file_sdf_opsin, sdf_append=sdf_append,
                                                 standardize_mols=standardize_mols)
            if not separated_output:
                opsin_converted = iter(opsin_converted["content"])
        else:
            self.logger.warning("Nothing to convert with OPSIN.")

        if separated_output:
            return ocsr, ner, opsin_converted

        self.logger.info("Joining results...")
        results = []

        for ent in ocsr["content"]:
            if annotate:
                results.append(OrderedDict([("source", "osra"), ("type", "2d_structure"), ("page", ent["page"]),
                                            ("abbreviation", ""), ("entity", ""), ("smiles", ent["smiles"]),
                                            ("inchi", ent["inchi"]), ("inchikey", ent["inchikey"]), ("opsin_error", ""),
                                            ("pch_cids_by_name", ""), ("chs_cids_by_name", ""),
                                            ("pch_cids_by_inchikey", ent["pch_cids_by_inchikey"]), ("chs_cids_by_inchikey", ent["chs_cids_by_inchikey"]),
                                            ("pch_cids_by_smiles", ent["pch_cids_by_smiles"]), ("chs_cids_by_smiles", ent["chs_cids_by_smiles"]),
                                            ("pch_cids_by_inchi", ent["pch_cids_by_inchi"]), ("chs_cids_by_inchi", ent["chs_cids_by_inchi"]),
                                            ("pch_cids_by_formula", ""),
                                            ("pch_iupac_name", ent["pch_iupac_name"]), ("chs_common_name", ent["chs_common_name"]),
                                            ("pch_synonyms", ent["pch_synonyms"])]))
            else:
                results.append(OrderedDict([("source", "osra"), ("type", "2d_structure"), ("page", ent["page"]),
                                            ("abbreviation", ""), ("entity", ""), ("smiles", ent["smiles"]),
                                            ("inchi", ent["inchi"]), ("inchikey", ent["inchikey"]), ("opsin_error", "")]))
        for ent in ner["content"]:
            if ent["type"] in opsin_types:
                ent_opsin = next(opsin_converted)
                new_ent = OrderedDict([("source", "chemspot"), ("type", ent["type"]), ("page", ent["page"]),
                                            ("abbreviation", ent["abbreviation"]), ("entity", ent["entity"]),
                                            ("smiles", ent_opsin["smiles"]), ("inchi", ent_opsin["inchi"]),
                                            ("inchikey", ent_opsin["inchikey"]), ("opsin_error", ent_opsin["error"])])
            else:
                new_ent = OrderedDict([("source", "chemspot"), ("type", ent["type"]), ("page", ent["page"]),
                                            ("abbreviation", ent["abbreviation"]), ("entity", ent["entity"]),
                                            ("smiles", ""), ("inchi", ""), ("inchikey", ""), ("opsin_error", "")])
            if annotate:
                new_ent.update(OrderedDict([("pch_cids_by_name", ent["pch_cids_by_name"]), ("chs_cids_by_name", ent["chs_cids_by_name"]),
                                            ("pch_cids_by_inchikey", ent["pch_cids_by_inchikey"]), ("chs_cids_by_inchikey", ent["chs_cids_by_inchikey"]),
                                            ("pch_cids_by_smiles", ent["pch_cids_by_smiles"]), ("chs_cids_by_smiles", ent["chs_cids_by_smiles"]),
                                            ("pch_cids_by_inchi", ent["pch_cids_by_inchi"]), ("chs_cids_by_inchi", ent["chs_cids_by_inchi"]),
                                            ("pch_cids_by_formula", ent["pch_cids_by_formula"]),
                                            ("pch_iupac_name", ent["pch_iupac_name"]), ("chs_common_name", ent["chs_common_name"]),
                                            ("pch_synonyms", ent["pch_synonyms"])]))
            results.append(new_ent)

        if results:
            if output_file:
                self.logger.info("Writing results to CSV file...")
                dict_to_csv(results, output_file=output_file, csv_delimiter=csv_delimiter, write_header=write_header)
        elif not results and output_file:
            self.logger.info("No extraction results, writing empty CSV file...")
            write_empty_file(output_file, csv_delimiter=csv_delimiter,
                             header=["source", "type", "page", "abbreviation", "entity", "smiles", "inchi", "inchikey", "opsin_error"],
                             write_header=write_header)

        return results
