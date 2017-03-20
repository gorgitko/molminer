from .AbstractLinker import AbstractLinker
from .utils import common_subprocess, dict_to_csv, write_empty_file

from rdkit.Chem import MolFromSmiles, MolToSmiles, MolFromInchi, MolToInchi, InchiToInchiKey, SDWriter, MolToMolBlock
from molvs import Standardizer

from collections import OrderedDict
import logging
from typing import Union
import re
import os


logging.basicConfig(format="[%(levelname)s - %(filename)s:%(funcName)s:%(lineno)s] %(message)s")
verbosity_levels = {
    0: 100,
    1: logging.WARNING,
    2: logging.INFO
}


class OPSIN(AbstractLinker):
    """
    Represents the OPSIN software and acts as a linker between Python and command-line interface of OPSIN.
    OPSIN version: 2.2.0

    OPSIN is a software for converting IUPAC names to linear notation (SMILES, InCHI etc.). It reads names from stdin
    or from input file where on each line is one IUPAC name.

    More information here: http://opsin.ch.cam.ac.uk/

    **To show the meaning of options:** ::

        opsin = OPSIN()
        print(opsin.help())  # this will show the output of "$ opsin -h"
        print(opsin._OPTIONS_REAL)  # this will show the mapping between OPSIN class and real OPSIN parameters

    Attributes
    ----------
    _OPTIONS_REAL : dict
        Internal dict which maps the passed options to real OSRA command-line arguments.
    options : dict
        Get or set options.
    options_internal : dict
        Return dict with options having internal names.
    path_to_binary : str
        Path to OPSIN binary (JAR file).

    Methods
    -------
    process
        Process the input file with OPSIN.
    help
        Return OPSINS help message.
    """

    _OPTIONS_REAL = {
        "allow_acids_without_acid": ("--allowAcidsWithoutAcid", ""),
        "detailed_failure_analysis": ("--detailedFailureAnalysis", ""),
        "output_format": ("--output", "{}"),
        "allow_radicals": ("--allowRadicals", ""),
        "allow_uninterpretable_stereo": ("--allowUninterpretableStereo", ""),
        "opsin_verbose": ("--verbose", ""),
        "wildcard_radicals": ("--wildcardRadicals", ""),
    }

    PLURAL_PATTERN = re.compile(r"(nitrate|bromide|chloride|iodide|amine|ketoxime|ketone|oxime)s", flags=re.IGNORECASE)
    logger = logging.getLogger("opsin")

    def __init__(self,
                 path_to_binary: str = "opsin",
                 allow_acids_without_acid: bool = True,
                 detailed_failure_analysis: bool = True,
                 output_format: str = "smi",
                 allow_radicals: bool = True,
                 allow_uninterpretable_stereo: bool = True,
                 opsin_verbose: bool = False,
                 wildcard_radicals: bool = False,
                 plural_pattern: str = None,
                 verbosity: int = 1):
        """
        Parameters
        ----------
        path_to_binary : str
        allow_acids_without_acid : bool
            Allows interpretation of acids without the word acid e.g. "acetic".
        detailed_failure_analysis : bool
            Enables reverse parsing to more accurately determine why parsing failed.
        output_format : str
            | Sets OPSIN's output format (default smi). Values: "cml", "smi", "extendedsmi", "inchi", "stdinchi", "stdinchikey"
            | Can be temporarily overriden in self.process method.
        allow_radicals : bool
            Enables interpretation of radicals.
        allow_uninterpretable_stereo : bool
            Allows stereochemistry uninterpretable by OPSIN to be ignored.
        opsin_verbose : bool
        wildcard_radicals : bool
            Radicals are output as wildcard atoms.
        plural_pattern : str
            Regex pattern to replace plurals. Default regex is in static attribute PLURAL_PATTERN.
        verbosity : int
            This class's verbosity. Values: 0, 1, 2
        """

        if verbosity > 2:
            verbosity = 2
        elif verbosity not in verbosity_levels:
            verbosity = 1
        self.logger.setLevel(verbosity_levels[verbosity])

        self.path_to_binary = path_to_binary
        _, self.options, self.options_internal = self.build_commands(locals(),
                                                                     self._OPTIONS_REAL,
                                                                     path_to_binary)
        if plural_pattern:
            self.plural_pattern = re.compile(plural_pattern, flags=re.IGNORECASE)
        else:
            self.plural_pattern = self.PLURAL_PATTERN

    def set_options(self, options: dict):
        """
        Sets the options passed in dict. Keys are the same as optional parameters in OPSIN constructor (__init__()).

        Parameters
        ----------
        options
            Dict of new options.
        """

        _, self.options, self.options_internal = self.build_commands(options, self._OPTIONS_REAL, self.path_to_binary)

    def help(self) -> str:
        """
        Returns
        -------
        str
            OPSIN help message.
        """

        stdout, stderr, _ = common_subprocess([self.path_to_binary, "-h"])

        if stderr:
            return stderr
        else:
            return stdout

    def normalize_iupac(self, iupac_names: Union[str, list]) -> Union[str, list]:
        """
        Normalize IUPAC names:

        - remove plurals ("nitrates" -> "nitrate")
        - first letter lowercase ("Ammonium Nitrate" -> "ammonium nitrate")

        Parameters
        ----------
        iupac_names : str or list
            If str, one IUPAC name per line.

        Returns
        -------
        str or list
        """

        return_list = True
        if isinstance(iupac_names, str):
            iupac_names = iupac_names.split("\n")
            return_list = False

        norm_names = []

        for name in iupac_names:
            new_name = re.sub(self.plural_pattern, r"\1", name)
            new_name = " ".join(map(lambda s: s[:1].lower() + s[1:] if s else '',
                                         [x.strip() for x in new_name.split()]))
            norm_names.append(new_name)

        return norm_names if return_list else "\n".join(norm_names)

    def process(self,
                input: Union[str, list] = "",
                input_file: str = "",
                output_file: str = "",
                output_file_sdf: str = "",
                output_file_cml: str = "",
                sdf_append: bool = False,
                format_output: bool = True,
                opsin_output_format: str = "",
                output_formats: list = None,
                write_header: bool = True,
                dry_run: bool = False,
                csv_delimiter: str = ";",
                standardize_mols: bool = True,
                normalize_plurals: bool = True) -> OrderedDict:
        r"""
        Process the input file with OPSIN.

        Parameters
        ----------
        input : str or list
            | str: String with IUPAC names, one per line.
            | list: List of IUPAC names.
        input_file : str
            Path to file to be processed by OPSIN. One IUPAC name per line.
        output_file : str
            File to write output in.
        output_file_sdf : str
            File to write SDF output in.
        output_file_cml : str
            | File to write CML (Chemical Markup Language) output in. `opsin_output_format` must be "cml".
            | Not supported by RDKit so standardization and conversion to other formats cannot be done.
        sdf_append : bool
            If True, append new molecules to existing SDF file or create new one if doesn't exist.
        format_output : bool
            | If True, the value of "content" key of returned dict will be list of OrderedDicts with keys:
            | "iupac", <output formats>, ..., "error"
            | If True and `output_file` is set it will be created as CSV file with columns: "iupac", <output formats>, ..., "error"
            | If False, the value of "content" key of returned dict will be None.
        opsin_output_format : str
            | Output format from OPSIN. Temporarily overrides the option `output_format` set during instantiation (in __init__).
            | Choices: "cml", "smi", "extendedsmi", "inchi", "stdinchi", "stdinchikey"
        output_formats : list
            | If True and `format_output` is also True, this specifies which molecule formats will be output.
            | You can specify more than one format, but only one format from OPSIN. This format must be also set with `output_format` in __init__
              or with `osra_output_format` here.
            | Default value: ["smiles"]

            +-----------------------+-----------------------+--------------------------------------------------------------------------------------------+
            |         Value         |         Source        |                                            Note                                            |
            +=======================+=======================+============================================================================================+
            |         smiles        |         RDKit         |                                          canonical                                         |
            +-----------------------+-----------------------+--------------------------------------------------------------------------------------------+
            |      smiles_opsin     |     OPSIN ("smi")     |                                           SMILES                                           |
            +-----------------------+-----------------------+--------------------------------------------------------------------------------------------+
            | smiles_extended_opsin | OPSIN ("extendedsmi") |                          Extended SMILES. Not supported by RDKit.                          |
            +-----------------------+-----------------------+--------------------------------------------------------------------------------------------+
            |         inchi         |         RDKit         | Not every molecule can be converted to InChI (it doesn`t support wildcard characters etc.) |
            +-----------------------+-----------------------+--------------------------------------------------------------------------------------------+
            |      inchi_opsin      |    OPSIN ("inchi")    |                                            InChI                                           |
            +-----------------------+-----------------------+--------------------------------------------------------------------------------------------+
            |     stdinchi_opsin    |   OPSIN ("stdinchi")  |                                       standard InChI                                       |
            +-----------------------+-----------------------+--------------------------------------------------------------------------------------------+
            |        inchikey       |         RDKit         |      The same applies as for "inchi". Also molecule cannot be created from InChI-key.      |
            +-----------------------+-----------------------+--------------------------------------------------------------------------------------------+
            |   stdinchikey_opsin   | OPSIN ("stdinchikey") |               Standard InChI-key. Cannot be used by RDKit to create molecule.              |
            +-----------------------+-----------------------+--------------------------------------------------------------------------------------------+
            |          sdf          |         RDKit         |                     If present, an additional SDF file will be created.                    |
            +-----------------------+-----------------------+--------------------------------------------------------------------------------------------+

        write_header : bool
            If True and if `output_file` is set and `output_format` is True, write a CSV write_header.
        dry_run : bool
            If True, only return list of commands to be called by subprocess.
        csv_delimiter : str
            Delimiter for output CSV file.
        standardize_mols : bool
            If True and `format_output` is also True, use molvs (https://github.com/mcs07/MolVS) to standardize molecules.
        normalize_plurals : bool
            | If True, normalize plurals ("nitrates" -> "nitrate"). See OPSIN.PLURAL_PATTERNS for relating plurals. You can
              set your own regex pattern with `plural_patterns` in __init__.

        Returns
        -------
        dict
            Keys:

            - stdout: str ... standard output from OPSIN
            - stderr: str ... standard error output from OPSIN
            - exit_code: int ... exit code from OPSIN
            - content:

              - list of OrderedDicts ... when format_output is True. Fields: "iupac", <output formats>, ..., "error"
              - None ... when format_output is False
        """

        options_internal = self.options_internal.copy()
        opsin_nonreadable_formats = ["cml", "stdinchikey"]

        if input and input_file:
            input_file = ""
            self.logger.warning("Both 'input' and 'input_file' are set, but 'input' will be prefered.")
        elif not input and not input_file:
            raise ValueError("One of 'input' or 'input_file' must be set.")

        # OSRA output format check
        if opsin_output_format:
            options_internal["output_format"] = opsin_output_format
        else:
            opsin_output_format = options_internal["output_format"]

        opsin_valid_output_formats = {"cml": "cml_opsin",
                                      "smi": "smiles_opsin",
                                      "extendedsmi": "smiles_extended_opsin",
                                      "inchi": "inchi_opsin",
                                      "stdinchi": "stdinchi_opsin",
                                      "stdinchikey": "stdinchikey_opsin"}

        if opsin_output_format not in opsin_valid_output_formats:
            raise ValueError("Unknown OPSIN output format. Possible values: {}".format(list(opsin_valid_output_formats.keys())))

        if standardize_mols and opsin_output_format in opsin_nonreadable_formats:
            self.logger.warning("OPSIN output format is \"{}\", which cannot be used by RDKit.".format(opsin_output_format))

        # output formats check
        if not output_formats:
            output_formats = ["smiles"]
        else:
            if opsin_output_format == "stdinchikey":
                output_formats = ["stdinchikey_opsin"]
            elif opsin_output_format == "extendedsmi":
                output_formats = ["smiles_extended_opsin"]
            else:
                output_formats = sorted(list(set(output_formats)))
                possible_output_formats = ["smiles", "inchi", "inchikey", "sdf"]
                output_formats = [x for x in output_formats if x in possible_output_formats or x == opsin_valid_output_formats[opsin_output_format]]

        if normalize_plurals:
            if input_file:
                with open(input_file, mode="r", encoding="utf-8") as f:
                    input = "\n".join([x.strip() for x in f.readlines()])
                input_file = ""
            input = self.normalize_iupac(input)

        commands, _, _ = self.build_commands(options_internal, self._OPTIONS_REAL, self.path_to_binary)

        if input_file:
            commands.append(input)
            stdout, stderr, exit_code = common_subprocess(commands)
        elif input:
            if isinstance(input, list):
                input = "\n".join([x.strip() for x in input])
            stdout, stderr, exit_code = common_subprocess(commands, stdin=input)
        else:
            raise UserWarning("Input is empty.")

        if dry_run:
            return " ".join(commands)

        to_return = {"stdout": stdout, "stderr": stderr, "exit_code": exit_code, "content": None}

        if output_file_cml and opsin_output_format == "cml":
            with open(output_file_cml, mode="w", encoding="utf-8") as f:
                f.write(stdout)
            return to_return
        elif output_file_cml and opsin_output_format != "cml":
            self.logger.warning("Output file for CML is requested, but OPSIN output format is '{}'".format(opsin_output_format))

        if not format_output:
            if output_file:
                with open(output_file, mode="w", encoding="utf-8") as f:
                    f.write(stdout)
            return to_return

        compounds = []
        standardizer = Standardizer()
        empty_cols = OrderedDict([(x, "") for x in output_formats])

        if output_file_sdf:
            if sdf_append:
                if not os.path.isfile(output_file_sdf):
                    open(output_file_sdf, mode="w", encoding="utf-8").close()
                writer = SDWriter(open(output_file_sdf, mode="a", encoding="utf-8"))
            else:
                writer = SDWriter(output_file_sdf)

        stdout = stdout.split("\n")
        del stdout[-1]
        stderr = [x.strip() for x in stderr.split("\n")[1:] if x]  # remove first line of stderr because there is OPSIN message (y u du dis...)

        if input_file:
            with open(input_file, mode="r", encoding="utf-8") as f:
                lines = iter(f.readlines())
        else:
            lines = iter(input.split("\n"))

        mol_output_template = OrderedDict.fromkeys(["iupac"] + output_formats + ["error"])

        e = 0
        for i, line in enumerate(lines):
            line = line.strip()
            converted = stdout[i].strip()
            mol_output = mol_output_template.copy()

            if converted:
                if opsin_output_format == "stdinchikey":
                    compounds.append(OrderedDict([("iupac", line), ("stdinchikey_opsin", converted), ("error", "")]))
                    continue
                elif opsin_output_format == "extendedsmi":
                    compounds.append(OrderedDict([("iupac", line), ("smiles_extended_opsin", converted), ("error", "")]))
                    continue

                if opsin_output_format == "smi":
                    mol = MolFromSmiles(converted, sanitize=False if standardize_mols else True)
                elif opsin_output_format in ["inchi", "stdinchi"]:
                    mol = MolFromInchi(converted, sanitize=False if standardize_mols else True, removeHs=False if standardize_mols else True)

                if mol:
                    if standardize_mols:
                        try:
                            mol = standardizer.standardize(mol)
                        except ValueError as e:
                            self.logger.warning("Cannot standardize '{}': {}".format(MolToSmiles(mol), str(e)))

                    for f in output_formats:
                        if f == "smiles":
                            mol_output["smiles"] = MolToSmiles(mol, isomericSmiles=True)
                        elif f == "smiles_opsin" and opsin_output_format == "smi":
                            mol_output["smiles_opsin"] = converted
                        elif f == "inchi":
                            inchi = MolToInchi(mol)
                            if inchi:
                                mol_output["inchi"] = inchi
                            else:
                                mol_output["inchi"] = ""
                                self.logger.warning("Cannot convert to InChI: {}".format(converted))
                        elif f == "inchi_opsin" and opsin_output_format == "inchi":
                            mol_output["inchi_opsin"] = converted
                        elif f == "stdinchi_opsin" and opsin_output_format == "stdinchi":
                            mol_output["stdinchi_opsin"] = converted
                        elif f == "inchikey":
                            inchi = MolToInchi(mol)
                            if inchi:
                                mol_output["inchikey"] = InchiToInchiKey(inchi)
                            else:
                                mol_output["inchikey"] = ""
                                self.logger.warning("Cannot create InChI-key from InChI: {}".format(converted))
                        elif f == "stdinchikey_opsin" and opsin_output_format == "stdinchikey":
                            mol_output["stdinchikey_opsin"] = converted
                        elif f == "sdf":
                            mol_output["sdf"] = MolToMolBlock(mol, includeStereo=True)

                    if output_file_sdf:
                        writer.write(mol)

                    mol_output.update(OrderedDict([("iupac", line), ("error", "")]))
                else:
                    mol_output.update([("iupac", line), ("error", "Cannot convert to RDKit mol: {}".format(converted))])
                    mol_output.update(empty_cols)
                    self.logger.warning(compounds[-1].error)
            else:
                try:
                    error = stderr[e].strip()
                except IndexError:
                    error = ""

                mol_output.update([("iupac", line), ("error", error)])
                mol_output.update(empty_cols)
                e += 1
            compounds.append(mol_output)

        to_return["content"] = compounds

        if output_file and compounds:
            dict_to_csv(to_return["content"], output_file=output_file, csv_delimiter=csv_delimiter, write_header=write_header)
        elif output_file and not compounds:
            write_empty_file(output_file, csv_delimiter=csv_delimiter, header=list(mol_output_template.keys()), write_header=write_header)

        return to_return
