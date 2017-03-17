from .AbstractLinker import AbstractLinker
from .utils import common_subprocess, get_input_file_type, dict_to_csv, write_empty_file, pdf_to_images, get_temp_images

from rdkit.Chem import MolToInchi, MolToSmiles, InchiToInchiKey, MolFromSmiles, MolFromMolBlock, SDWriter, MolToMolBlock
from joblib import Parallel, delayed
from molvs import Standardizer

from pubchempy import get_compounds, BadRequestError, NotFoundError, PubChemHTTPError, ResponseParseError, ServerError, TimeoutError, PubChemPyError
from chemspipy import ChemSpider

from collections import ChainMap, OrderedDict
import logging
import tempfile
import os
from time import sleep


logging.basicConfig(format="[%(levelname)s - %(filename)s:%(funcName)s:%(lineno)s] %(message)s")
verbosity_levels = {
    0: 100,
    1: logging.WARNING,
    2: logging.INFO
}


class OSRA(AbstractLinker):
    """
    Represents the OSRA software and acts as a linker between Python and command-line interface of OSRA.
    OSRA version: 2.1.0

    OSRA is a software for extraction of 2D structures from various formats like PDF and images. It recognizes the
    position of structure in the source and then constructs its linear notation (SMILES, InCHI etc.).
    More information here: https://sourceforge.net/projects/osra/ (old website: https://cactus.nci.nih.gov/osra/)

    To show the meaning of options:
        osra = OSRA()
        print(osra.help())  # this will show the output of "$ osra -h"
        print(osra._OPTIONS_REAL)  # this will show the mapping between OSRA class and real OSRA parameters

    Attributes
    ----------
    _OPTIONS_REAL : dict
        Internal dict which maps the passed options to real OSRA command-line arguments.
    options : dict
        Get or set options.
    options_internal : dict
        Return dict with options having internal names.
    path_to_binary : str
        Path to OSRA binary.

    Methods
    -------
    process
        Process the input file with OSRA.
    help
        Return OSRA help message.
    version
        Return OSRA version.

    Notes
    -----
    --learn parameter is currently not supported, because its output is problematic to parse.
    """

    _OPTIONS_REAL = {
        #"print_learn_guess": ("--learn", ""),
        #"output_file": ("--write", "{}"),
        "size": ("--size", "{}"),
        "images_prefix": ("--output", "{}"),
        "osra_verbose": ("--verbose", ""),
        "debug": ("--debug", ""),
        "embedded_format": ("--embedded-format", "{}"),
        "output_format": ("--format", "{}"),
        "adaptive": ("--adaptive", ""),
        "jaggy": ("--jaggy", ""),
        "unpaper": ("--unpaper", "{}"),
        "gray_threshold": ("--threshold", "{}"),
        "resolution": ("--resolution", "{}"),
        "negate": ("--negate", ""),
        "rotate": ("--rotate", "{}"),
        "superatom_config_path": ("--superatom", "{}"),
        "spelling_config_path": ("--spelling", "{}")
    }

    # GraphicsMagick command to convert PDF to numbered PNG images
    GM_COMMAND = "gm convert -density {dpi} {input_file_path} +adjoin {trim} -quality 100 {temp_dir}/{input_file}-%d.png"
    logger = logging.getLogger("osra")

    def __init__(self,
                 path_to_binary: str = "osra",
                 #print_learn_guess: bool = False,
                 size: str = "",
                 osra_verbose: bool = False,
                 debug: bool = False,
                 embedded_format: str = "",
                 output_format: str = "can",
                 adaptive: bool = False,
                 jaggy: bool = False,
                 unpaper: int = 0,
                 gray_threshold: float = 0.0,
                 resolution: int = 300,
                 negate: bool = False,
                 rotate: int = 0,
                 superatom_config_path: str = "superatom.txt",
                 spelling_config_path: str = "spelling.txt",
                 verbosity: int = 1):
        """
        Parameters
        ----------
        path_to_binary : str
        size : str
            Resize image on output. <dimensions, 300x400>
        osra_verbose : bool
            Be verbose and print the program flow.
        debug : bool
            Print out debug information on spelling corrections.
        embedded_format : str
            Embedded format. One of <inchi/smi/can>.
        output_format : str
            Output format. One of <can/smi/sdf>.
        adaptive : bool
            Adaptive thresholding pre-processing, useful for low light/low contrast images.
        jaggy : bool
            Additional thinning/scaling down of low quality documents.
        unpaper : int
            Pre-process image with unpaper algorithm, rounds.
        gray_threshold : float
            Gray level threshold. Range: 0.2-0.8
        resolution : int
            Resolution in dots per inch (DPI).
        negate : bool
            Invert color (white on black).
        rotate : int
            Rotate image clockwise by specified number of degrees.
        superatom_config_path : str
            Path to superatom label map to SMILES.
        spelling_config_path : str
            Path to spelling correction dictionary.
        verbosity : int
            This class's verbosity. Values: 0, 1, 2
        """

        if verbosity > 2:
            verbosity = 2
        elif verbosity not in verbosity_levels:
            verbosity = 1
        self.logger.setLevel(verbosity_levels[verbosity])

        if superatom_config_path == "superatom.txt" and "OSRA_DATA_PATH" in os.environ:
            superatom_config_path = "{}/{}".format(os.environ["OSRA_DATA_PATH"], "superatom.txt")

        if spelling_config_path == "spelling.txt" and "OSRA_DATA_PATH" in os.environ:
            spelling_config_path = "{}/{}".format(os.environ["OSRA_DATA_PATH"], "spelling.txt")

        self.path_to_binary = path_to_binary
        _, self.options, self.options_internal = self.build_commands(locals(), self._OPTIONS_REAL, path_to_binary)

    def set_options(self, options: dict):
        """
        Sets the options passed in dict. Keys are the same as optional parameters in OSRA constructor (__init__).

        Parameters
        ----------
        options
            Dict of new options.
        """

        _, self.options, self.options_internal = self.build_commands(options, self._OPTIONS_REAL, self.path_to_binary)

    def version(self) -> str:
        """
        Returns
        -------
        str
            OSRA version.
        """

        stdout, stderr, _ = common_subprocess([self.path_to_binary, "--version"])

        if stderr:
            return stderr
        else:
            return stdout

    def help(self) -> str:
        """
        Returns
        -------
        str
            OSRA help message.
        """

        stdout, stderr, _ = common_subprocess([self.path_to_binary, "-h"])

        if stderr:
            return stderr
        else:
            return stdout

    def _process(self, input_file: str, commands: list, dry_run: bool = False, page: int = 1):
        """
        Process one file with OSRA.

        Parameters
        ----------
        input_file : str
        commands : list
        dry_run : bool

        Returns
        -------
        dict
        """

        commands = commands.copy()
        commands.append(input_file)

        if dry_run:
            return commands

        output = common_subprocess(commands)
        return {"stdout": output.stdout, "stderr": output.stderr, "exit_code": output.exit_code, "page": page}

    def process(self,
                input_file: str,
                output_file: str = "",
                output_file_sdf: str = "",
                sdf_append: bool = False,
                #images_prefix: str = "",
                format_output: bool = True,
                write_header: bool = True,
                osra_output_format: str = "",
                output_formats: list = None,
                dry_run: bool = False,
                csv_delimiter: str = ";",
                use_gm: bool = True,
                gm_dpi: int = 300,
                gm_trim: bool = True,
                n_jobs: int = -1,
                input_type: str = "",
                standardize_mols: bool = True,
                annotate: bool = True,
                chemspider_token: str = "",
                custom_page: int = 0) -> OrderedDict:
        """
        Process the input file with OSRA.

        Parameters
        ----------
        input_file : str
            Path to file to be processed by OSRA.
        output_file : str
            File to write output in.
        output_file_sdf : str
            File to write SDF output in. "sdf" output format hasn't to be in `output_formats` to write SDF output.
            If "sdf_osra" output format is requested, suffix "-osra.sdf" will be added.
        sdf_append : bool
            If True, append new molecules to existing SDF file or create new one if doesn't exist.
        NOT IMPLEMENTED | images_prefix : str
            Prefix for images of extracted compounds which will be written.
        format_output : bool
            If True, the value of "content" key of returned dict will be list of OrderedDicts.
            If True and `output_file` is set, the CSV file will be written.
            If False, the value of "content" key of returned dict will be None.
        write_header : bool
            If True and if `output_file` is set and `output_format` is True, write a CSV write_header.
        osra_output_format : str
            Output format from OSRA. Temporarily overrides the option `output_format` set during instantiation (in __init__).
            Choices: "smi", "can", "sdf"
            If "sdf", additional information like coordinates cannot be retrieved (not implemented yet).
        output_formats : list
            If True and `format_output` is also True, this specifies which molecule formats will be output.
            You can specify more than one format, but only one format from OSRA. This format must be also set with `output_format` in __init__
            or with `osra_output_format` here.
            When output produces by OSRA is unreadable by RDKit, you can at least have that output from OSRA.
                <Value>            <Source>        <Note>
                "smiles"           RDKit           canonical SMILES
                "smiles_osra"      OSRA ("smi")    SMILES
                "smiles_can_osra"  OSRA ("can")    canonical SMILES
                "inchi"            RDKit           Not every molecule can be converted to InChI (it doesn`t support wildcard characters etc.)
                "inchikey"         RDKit           The same applies as for "inchi".
                "sdf"              RDKit           If present, an additional SDF file will be created.
                "sdf_osra"         OSRA ("sdf")    If present, an additional SDF file will be created.
            Default value: ["smiles"]
        dry_run : bool
            If True, only return list of commands to be called by subprocess.
        csv_delimiter : str
            Delimiter for output CSV file.
        use_gm : bool
            If True, use GraphicsMagick to convert PDF to temporary PNG images before processing.
            If False, OSRA will use it's own conversion of PDF to image.
            Using gm is more reliable since OSRA (v2.1.0) is showing wrong information
            when converting directly from PDF (namely: coordinates, bond length and possibly more ones) and also there are sometimes
            incorrectly recognised structures.
        gm_dpi : int
            How many DPI will temporary PNG images have.
        gm_trim : bool
            If True, gm will trim the temporary PNG images.
        n_jobs : int
            If `use_gm` and input file is PDF, how many jobs to use for OSRA processing of temporary PNG images.
            If -1 all CPUs are used.
            If 1 is given, no parallel computing code is used at all, which is useful for debugging.
            For n_jobs below -1, (n_cpus + 1 + n_jobs) are used. Thus for n_jobs = -2, all CPUs but one are used.
        input_type : str
            When empty, input (MIME) type will be determined from magic bytes.
            Or you can specify "pdf" or "image" and magic bytes check will be skipped.
        standardize_mols : bool
            If True and `format_output` is also True, use molvs (https://github.com/mcs07/MolVS) to standardize molecules.
        annotate : bool
            If True, try to annotate entities in PubChem and ChemSpider. Compound IDs will be assigned by searching with
            each identifier, separately for SMILES, InChI etc.
            If entity has InChI key yet, prefer it in searching.
            If "*" is present in SMILES, skip annotation.
        chemspider_token : str
            Your personal token for accessing the ChemSpider API. Make account there to obtain it.
        custom_page : bool
            When `use_gm` is False, this will set the page for all extracted compounds.

        Returns
        -------
        dict
            Keys:
                stdout: str ... standard output from OSRA
                stderr: str ... standard error output from OSRA
                exit_code: int ... exit code from OSRA
                content:
                    list of OrderedDicts ... when `format_output` is True.
                    None ... when `format_output` is False
            If `osra_output_format` is "sdf", additional information like 'bond_length' cannot be retrieved.
            If `use_gm` is True then stdout, stderr and exit_code will be lists containing items from each temporary image
            extracted by OSRA.

        Notes
        -----
        Only with `format_output` set to True you can use molecule standardization and more molecule formats. Otherwise
        you will only get raw stdout from OSRA (which can also be written to file if `output_file` is set).
        """

        options_internal = self.options_internal.copy()
        osra_smiles_outputs = ["smi", "can"]

        # OSRA output format check
        if osra_output_format:
            options_internal["output_format"] = osra_output_format
        else:
            osra_output_format = options_internal["output_format"]

        osra_valid_output_formats = {"can": "smiles_can_osra",
                                     "smi": "smiles_osra",
                                     "sdf": "sdf_osra"}
        if osra_output_format not in osra_valid_output_formats:
            raise ValueError("Unknown OSRA output format. Possible values: {}".format(osra_valid_output_formats.values()))

        if osra_output_format == "sdf":
            self.logger.warning("OSRA's output format is set to \"sdf\" so additional information like coordinates cannot be retrieved.")

        # output formats check
        is_output_sdf = False
        is_output_sdf_osra = False
        if not output_formats:
            output_formats = ["smiles"]
        else:
            output_formats = sorted(list(set(output_formats)))
            possible_output_formats = ["smiles", "inchi", "inchikey", "sdf"]
            output_formats = [x for x in output_formats if
                              x in possible_output_formats or x == osra_valid_output_formats[osra_output_format]]

            if ("sdf" in output_formats or "sdf_osra" in output_formats) and not output_file_sdf:
                self.logger.warning("Cannot write SDF output: 'output_file_sdf' is not set.")
            if output_file_sdf:
                is_output_sdf = True
            if "sdf_osra" in output_formats and osra_output_format == "sdf" and output_file_sdf:
                is_output_sdf_osra = True
            if ("smiles_osra" in output_formats or "smiles_can_osra" in output_formats) and osra_output_format == "sdf":
                try:
                    output_formats.remove("smiles_osra")
                except ValueError:
                    pass
                try:
                    output_formats.remove("smiles_can_osra")
                except ValueError:
                    pass
                self.logger.warning("SMILES or canonical SMILES output from OSRA is requested, but OSRA's output format is \"{}\".".format(osra_output_format))

        # input file type check
        possible_input_types = ["pdf", "image"]
        if not input_type:
            input_type = get_input_file_type(input_file)
            if input_type not in possible_input_types:
                use_gm = False
                self.logger.warning("Input file MIME type ('{}') is not one of {}. You can specify 'input_type' directly (see docstring).".format(input_type, possible_input_types))
        elif input_type not in possible_input_types:
                raise ValueError("Possible 'input_type' values are {}".format(possible_input_types))

        #options = ChainMap({k: v for k, v in {"images_prefix": images_prefix}.items() if v},
        #                   options_internal)

        if annotate:
            if not chemspider_token:
                self.logger.warning("Cannot perform annotation in ChemSpider: 'chemspider_token' is empty.")
            [output_formats.append(x) for x in ["smiles", "inchi", "inchikey"] if x not in output_formats]
            output_formats = sorted(output_formats)

        commands, _, _ = self.build_commands(options_internal, self._OPTIONS_REAL, self.path_to_binary)
        commands.extend(["--bond", "--coordinates", "--page", "--guess", "--print"])

        if dry_run:
            return " ".join(commands)

        osra_output_list = []
        if input_type == "image" or not use_gm:
            osra_output_list.append(self._process(input_file, commands, page=custom_page if custom_page else 1))
        elif input_type == "pdf":
            with tempfile.TemporaryDirectory() as temp_dir:
                stdout, stderr, exit_code = pdf_to_images(input_file, temp_dir, dpi=gm_dpi, trim=gm_trim)
                osra_output_list = Parallel(n_jobs=n_jobs)(
                    delayed(self._process)(temp_image_file, commands, page=page)
                                           for temp_image_file, page in get_temp_images(temp_dir))

        # summarize OSRA results
        to_return = {"stdout": [], "stderr" :[], "exit_code": [], "content": None, "pages": []}
        for result in osra_output_list:
            if result["stdout"]:
                to_return["stdout"].append(result["stdout"])
                to_return["stderr"].append(result["stderr"])
                to_return["exit_code"].append(result["exit_code"])
                to_return["pages"].append(result["page"])

        if not format_output:
            if output_file:
                with open(output_file, mode="w", encoding="utf-8") as f:
                    f.write("\n".join(to_return["stdout"]))
            return to_return

        output_cols = OrderedDict([
            ("bond_length", 1),
            ("resolution", 2),
            ("confidence", 3),
            ("page", 4),
            ("coordinates", 5)
        ])

        if osra_output_format in osra_smiles_outputs:
            compound_template_dict = OrderedDict.fromkeys(output_formats + list(output_cols.keys()))
        else:
            compound_template_dict = OrderedDict.fromkeys(["page"] + output_formats)

        if any(to_return["stdout"]):
            if standardize_mols:
                standardizer = Standardizer()

            compounds = []

            if is_output_sdf:
                if sdf_append:
                    if not os.path.isfile(output_file_sdf):
                        open(output_file_sdf, mode="w", encoding="utf-8").close()
                    writer = SDWriter(open(output_file_sdf, mode="a", encoding="utf-8"))
                else:
                    writer = SDWriter(output_file_sdf)

            for output, page in zip(to_return["stdout"], to_return["pages"]):
                if osra_output_format in osra_smiles_outputs:
                    lines = [x.strip() for x in output.split("\n") if x]
                else:
                    lines = [x for x in output.split("$$$$") if x.strip()]

                for line in lines:
                    """
                    # so much problems with --learn
                    # we can't simply split output by " " when --learn is present, because its output is like "1,2,2,2 1"
                    if "learn" in filtered_cols:
                        learn_start = filtered_cols.index("learn") + 1 #  "smiles" col isn't in output_cols
                        learn_end = filtered_cols.index("learn") + 1 + 3
                        line[learn_start:learn_end] = [" ".join(line[learn_start:learn_end])]
                    """

                    if not line:
                        continue

                    if osra_output_format in osra_smiles_outputs:
                        line = [x.strip() for x in line.split()]
                        if custom_page:
                            line[output_cols["page"]] = custom_page
                        elif use_gm:
                            line[output_cols["page"]] = page
                        mol = MolFromSmiles(line[0], sanitize=False if standardize_mols else True)
                    elif osra_output_format == "sdf":
                        line = "\n" + line.strip()
                        mol = MolFromMolBlock(line, strictParsing=False, sanitize=False if standardize_mols else True,
                                              removeHs=False if standardize_mols else True)

                    if mol:
                        compound = compound_template_dict.copy()

                        if standardize_mols:
                            try:
                                mol = standardizer.standardize(mol)
                            except ValueError as e:
                                self.logger.warning("Cannot standardize '{}': {}".format(MolToSmiles(mol), str(e)))

                        for f in output_formats:
                            if f == "smiles":
                                compound["smiles"] = MolToSmiles(mol, isomericSmiles=True)
                            elif f == "smiles_osra" and osra_output_format == "smi":
                                compound["smiles_osra"] = line[0]
                            elif f == "smiles_can_osra" and osra_output_format == "can":
                                compound["smiles_can_osra"] = line[0]
                            elif f == "inchi":
                                inchi = MolToInchi(mol)
                                if inchi:
                                    compound["inchi"] = inchi
                                else:
                                    compound["inchi"] = ""
                                    self.logger.warning("Cannot convert to InChI: {}".format(MolToSmiles(mol)))
                            elif f == "inchikey":
                                inchi = MolToInchi(mol)
                                if inchi:
                                    compound["inchikey"] = InchiToInchiKey(inchi)
                                else:
                                    compound["inchikey"] = ""
                                    self.logger.warning("Cannot create InChI-key from InChI: {}".format(MolToSmiles(mol)))
                            elif f == "sdf":
                                compound["sdf"] = MolToMolBlock(mol, includeStereo=True)
                            elif f == "sdf_osra":
                                compound["sdf_osra"] = line

                        if is_output_sdf:
                            writer.write(mol)

                        if osra_output_format in osra_smiles_outputs:
                            compound.update([(x[0], x[1]) for x in zip(list(output_cols.keys()), line[1:])])
                        else:
                            compound["page"] = page if use_gm else custom_page if custom_page else 1

                        compounds.append(compound)
                    else:
                        self.logger.warning("Cannot convert to RDKit mol: " + line[0])

            if is_output_sdf_osra:
                with open(output_file_sdf + "-osra.sdf", mode="w", encoding="utf-8") as f:
                    f.write("".join(to_return["stdout"]))

            to_return["content"] = sorted(compounds, key=lambda x: x["page"])

            if annotate:
                chemspider = ChemSpider(chemspider_token)

                for i, ent in enumerate(to_return["content"]):
                    self.logger.info("Annotating entity {}/{}...".format(i + 1, len(to_return["content"])))
                    ent.update(OrderedDict([("pch_cids_by_inchikey", ""), ("chs_cids_by_inchikey", ""),
                                            ("pch_cids_by_smiles", ""), ("chs_cids_by_smiles", ""),
                                            ("pch_cids_by_inchi", ""), ("chs_cids_by_inchi", ""),
                                            ("pch_iupac_name", ""), ("chs_common_name", ""),
                                            ("pch_synonyms", "")]))

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
                                ent["pch_cids_by_inchikey"] = "\"{}\"".format(",".join([str(c.cid) for c in results]))
                        except (BadRequestError, NotFoundError, PubChemHTTPError, ResponseParseError, ServerError, TimeoutError, PubChemPyError):
                            pass

                        results = chemspider.search(ent["inchikey"])
                        if results:
                            if len(results) == 1:
                                result = results[0]
                                ent["chs_common_name"] = result.common_name
                            ent["chs_cids_by_inchikey"] = "\"{}\"".format(",".join([str(c.csid) for c in results]))
                    else:
                        for search_field, col_pch, col_chs in [("smiles", "pch_cids_by_smiles", "chs_cids_by_smiles"),
                                                               ("inchi", "pch_cids_by_inchi", "chs_cids_by_inchi")]:
                            results_pch = []
                            results_chs = []

                            if search_field == "smiles" and "smiles" in ent and ent["smiles"] and "*" not in ent["smiles"]:
                                try:
                                    results_pch = get_compounds(ent["smiles"], "smiles")
                                except (BadRequestError, NotFoundError, PubChemHTTPError, ResponseParseError, ServerError, TimeoutError, PubChemPyError):
                                    pass
                                results_chs = chemspider.search(ent["smiles"])
                            elif search_field == "inchi" and "inchi" in ent and ent["inchi"]:
                                try:
                                    results_pch = get_compounds(ent["inchi"], "inchi")
                                except (BadRequestError, NotFoundError, PubChemHTTPError, ResponseParseError, ServerError, TimeoutError, PubChemPyError):
                                    pass
                                results_chs = chemspider.search(ent["inchi"])

                            if results_pch:
                                ent[col_pch] = "\"{}\"".format(",".join([str(c.cid) for c in results_pch]))
                            if results_chs:
                                ent[col_chs] = "\"{}\"".format(",".join([str(c.csid) for c in results_chs]))

                            sleep(0.5)

            if output_file:
                dict_to_csv(to_return["content"], output_file=output_file, csv_delimiter=csv_delimiter, write_header=write_header)

            if is_output_sdf:
                writer.close()
        elif not any(to_return["stdout"]) and output_file:
            write_empty_file(output_file, csv_delimiter=csv_delimiter, header=list(compound_template_dict.keys()), write_header=write_header)

        return to_return
