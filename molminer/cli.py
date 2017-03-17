from . import __version__, ChemSpot, OSRA, OPSIN, Extractor
from .utils import dict_to_csv, eprint

import click


def add_options(options):
    def _add_options(func):
        for option in reversed(options):
            func = option(func)
        return func
    return _add_options


def get_kwargs(options, kwargs):
    return {kwargs[option]: options[option] for option in options if option in kwargs}


OPTS_COMMON_ALL = [
    click.option("-o", "--output", show_default=True, default="", type=click.STRING,
                 help="File to write output in."),
    click.option("-d", "--delimiter", show_default=True, default=";", type=click.STRING,
                 help="CSV delimiter. To pass special chars like tab '\\t' use $'\\t' in shell (Bash). "
                      "See http://www.gnu.org/software/bash/manual/bashref.html#Single-Quotes for more info."),
    click.option("--no-header", show_default=True, default=False, is_flag=True,
                 help="Don't write CSV header."),
    click.option("-v", "--verbosity", show_default=True, default=1, type=click.IntRange(min=0, max=2, clamp=True),
                 help="0, 1 or 2")
]

OPTS_COMMON_OCSR_NER_CONVERT = [
    click.option("--dry-run", show_default=True, is_flag=True,
                 help="Only print shell commands which normally would be executed. Useful for debugging -- "
                      "by using these commands in shell you can get raw stdout and stderr from individual SWs."),
    click.option("--raw-output", show_default=True, default=False, is_flag=True,
                 help="Print raw stdout and stderr (to stderr) of SW.")
]

OPTS_COMMON_NER_EXTRACT = [
    click.option("--opsin-types", type=click.STRING, show_default=True, default="SYSTEMATIC",
                 help="ChemSpot entity types, separated by commas (','). Entities of these types will be converted with OPSIN. "
                      "OPSIN is designed to convert IUPAC names to linear notation (SMILES etc.) so default value is "
                      "'SYSTEMATIC' (these should be only IUPAC names). "
                      "ChemSpot entity types: 'SYSTEMATIC', 'IDENTIFIER', 'FORMULA', 'TRIVIAL', 'ABBREVIATION', 'FAMILY', 'MULTIPLE'"),
    click.option("--remove-duplicates", show_default=True, is_flag=True, default=False,
                 help="Remove duplicated chemical entities."),
    click.option("--lang", type=click.STRING, show_default=True, default="eng",
                 help="Language which will Tesseract use for OCR. Available languages: https://github.com/tesseract-ocr/tessdata "
                      "Multiple languages can be specified with '+' character, e.g. 'eng+bul+fra'."),
    click.option("--tessdata-path", type=click.STRING, show_default=True, default="",
                 help="Path to Tesseract language data, if not set in TESSDATA_PREFIX environment variable."),
    click.option("--annotation-sleep", type=click.INT, default=2, show_default=True,
                 help="How many seconds to sleep between annotation of each entity. It's for preventing overloading of databases.")
]

OPTS_COMMON_OCSR_CONVERT_EXTRACT = [
    click.option("--sdf-append", show_default=True, is_flag=True, default=False,
                 help="Append new molecules to existing SDF file or create new one if doesn't exist.")
]

OPTS_COMMON_OCSR_EXTRACT = [
    click.option("--no-use-gm", show_default=True, is_flag=True, default=False,
                 help="Don't use GraphicsMagick to convert PDF to temporary PNG images before processing. Then will OSRA use "
                      "it's own conversion of PDF to image. "
                      "Using GM is more reliable, because OSRA (v2.1.0) is showing wrong information "
                      "when converting directly from PDF (namely: coordinates, bond length and possibly more ones) and also there are sometimes "
                      "incorrectly recognised structures."),
    click.option("-j", "--jobs", show_default=True, default=-1, type=click.INT,
                 help="How many jobs to use for processing. '-1' to use all CPU cores. '-2' to use all CPU cores minus one.")
]

OPTS_COMMON_OCSR_CONVERT = [
    click.option("--sdf-output", type=click.STRING, default="", show_default=True,
                 help="File to write SDF output in.")
]

OPTS_COMMON_OCSR_NER_EXTRACT = [
    click.option("--no-standardize", show_default=True, default=False, is_flag=True,
                 help="Don't standardize molecules using MolVS (https://github.com/mcs07/MolVS)."),
    click.option("--chemspider-token", type=click.STRING, default="", show_default=True,
                 help="Your personal token for accessing the ChemSpider API (needed for annotation). Make account there to obtain it."),
    click.option("--no-annotation", show_default=True, is_flag=True, default=False,
                 help="Don't do annotation of entities in PubChem and ChemSpider.")
]

OPTS_CONVERT_INIT = [
    # INIT
    click.option("--opsin-path", show_default=True, default="opsin", type=click.STRING,
                 help="Path to OPSIN run script."),
    click.option("--opsin-no-allow-acids-without-acid", show_default=True, is_flag=True, default=False,
                 help="Don't allow interpretation of acids without the word acid e.g. 'acetic'."),
    click.option("--opsin-no-detailed-failure-analysis", show_default=True, is_flag=True, default=False,
                 help="Don't enable reverse parsing to more accurately determine why parsing failed."),
    click.option("--opsin-no-allow-radicals", show_default=True, is_flag=True, default=False,
                 help="Don't enable interpretation of radicals."),
    click.option("--opsin-no-allow-uninterpretable-stereo", show_default=True, is_flag=True, default=False,
                 help="Don't allow stereochemistry uninterpretable by OPSIN to be ignored."),
    click.option("--opsin-wildcard-radicals", show_default=True, is_flag=True, default=False,
                 help="Radicals are output as wildcard atoms.")
]

OPTS_CONVERT_PROCESS = [
    # PROCESS
    click.option("--no-normalize-plurals", show_default=True, is_flag=True, default=False,
                 help="Don't normalize some plurals before converting to linear notation, e.g. 'nitrates' -> 'nitrate'.")
]

KWARGS_OPSIN_INIT = {
    "opsin_path": "path_to_binary",
    "opsin_no_allow_acids_without_acid": "allow_acids_without_acid",
    "opsin_no_detailed_failure_analysis": "detailed_failure_analysis",
    "opsin_no_allow_radicals": "allow_radicals",
    "opsin_no_allow_uninterpretable_stereo": "allow_uninterpretable_stereo",
    "opsin_wildcard_radicals": "wildcard_radicals",
    "verbosity": "verbosity"
}

KWARGS_OPSIN_PROCESS = {
    "input_file": "input_file",
    "output": "output_file",
    "sdf_output": "output_file_sdf",
    "sdf_append": "sdf_append",
    "no_header": "write_header",
    "dry_run": "dry_run",
    "delimiter": "csv_delimiter",
    "no_standardize": "standardize_mols",
    "no_normalize_plurals": "normalize_plurals"
}

OPTS_NER_INIT = [
    # INIT
    click.option("--chs-path", show_default=True, default="chemspot", type=click.STRING,
                 help="Path to ChemSpot run script."),
    click.option("--chs-crf", type=click.STRING, default="", show_default=True,
                 help="Path to a CRF model file (internal default model file will be used if not provided)."),
    click.option("--chs-nlp", type=click.STRING, default="", show_default=True,
                 help="Path to a OpenNLP sentence model file (internal default model file will be used if not provided)."),
    click.option("--chs-dict", type=click.STRING, default="", show_default=True,
                 help="Path to a zipped set of brics dictionary automata. Disabled by default, use 'dict.zip' for default dictionary."),
    click.option("--chs-ids", type=click.STRING, default="", show_default=True,
                 help="Path to a zipped tab-separated text file representing a map of terms to ids. Disabled by default, use 'ids.zip' for default ids."),
    click.option("--chs-multiclass", type=click.STRING, default="multiclass.bin", show_default=True,
                 help="Path to a multi-class model file. Enabled by default."),
    click.option("--chs-iob", show_default=True, is_flag=True, default=False,
                 help="If this flag is set, the output will be converted into the IOB format."),
    click.option("--chs-memory", type=click.INT, default=8, show_default=True,
                 help="Maximum amount of memory [GB] which can be allocated for ChemSpot.")
]

OPTS_NER_PROCESS = [
    # PROCESS
    click.option("--no-normalize-text", show_default=True, is_flag=True, default=False,
                 help="Don't normalize text before performing NER (strongly not recommended)."),
    click.option("--paged-text", show_default=True, is_flag=True, default=False,
                 help="If 'input_type' is \"text\", try to assign pages to chemical entities. "
                      "ASCII control character 12 (Form Feed, '\\f') is expected between pages."),
    click.option("--no-convert-ions", show_default=True, is_flag=True, default=False,
                 help="Don't try to convert ion entities (e.g. 'Ni(II)') to SMILES. Entities matching ion regex won't be converted with OPSIN.")
]

KWARGS_CHS_INIT = {
    "chs_path": "path_to_binary",
    "chs_crf": "path_to_crf",
    "chs_nlp": "path_to_nlp",
    "chs_dict": "path_to_dict",
    "chs_ids": "path_to_ids",
    "chs_multiclass": "path_to_multiclass",
    "tessdata_path": "tessdata_path",
    "chs_memory": "max_memory",
    "verbosity": "verbosity"
}

KWARGS_CHS_PROCESS = {
    "input_file": "input_file",
    "output": "output_file",
    "input_type": "input_type",
    "lang": "lang",
    "paged_text": "paged_text",
    "opsin_types": "opsin_types",
    "no_standardize": "standardize_mols",
    "no_convert_ions": "convert_ions",
    "no_header": "write_header",
    "chs_iob": "iob_format",
    "dry_run": "dry_run",
    "delimiter": "csv_delimiter",
    "no_normalize_text": "normalize_text",
    "remove_duplicates": "remove_duplicates",
    "no_annotation": "annotate",
    "annotation_sleep": "annotation_sleep",
    "chemspider_token": "chemspider_token"
}

OPTS_OCSR_INIT = [
    # INIT
    click.option("--osra-path", show_default=True, default="osra", type=click.STRING,
                 help="Path to OSRA binary."),
    click.option("--osra-size", type=click.STRING, default="", show_default=True,
                 help="Resize image on output. <dimensions, 300x400>"),
    click.option("--osra-adaptive", show_default=True, is_flag=True, default=False,
                 help="Adaptive thresholding pre-processing, useful for low light/low contrast images."),
    click.option("--osra-jaggy", show_default=True, is_flag=True, default=False,
                 help="Additional thinning/scaling down of low quality documents."),
    click.option("--osra-unpaper", type=click.INT, show_default=True, default=0,
                 help="Pre-process image with unpaper algorithm, rounds."),
    click.option("--osra-gray-threshold", type=click.FLOAT, show_default=True, default=0.0,
                 help="Gray level threshold. <0.2..0.8>"),
    click.option("--osra-resolution", type=click.INT, show_default=True, default=300,
                 help="Resolution in dots per inch."),
    click.option("--osra-negate", show_default=True, is_flag=True, default=False,
                 help="Invert color (white on black)."),
    click.option("--osra-rotate", show_default=True, default=0, type=click.IntRange(min=0, max=360, clamp=True),
                 help="Rotate image clockwise by specified number of degrees. <0..360>"),
    click.option("--osra-superatom-file", type=click.STRING, default="superatom.txt", show_default=True,
                 help="Path to superatom label map to SMILES."),
    click.option("--osra-spelling-file", type=click.STRING, default="spelling.txt", show_default=True,
                 help="Path to spelling correction dictionary.")
]

OPTS_OCSR_PROCESS = [
    # PROCESS
    click.option("--gm-dpi", type=click.INT, default=300, show_default=True,
                 help="How many DPI will temporary PNG images have."),
    click.option("--no-gm-trim", show_default=True, is_flag=True, default=False,
                 help="Don't trim the temporary PNG images.")
]

KWARGS_OSRA_INIT = {
    "osra_path": "path_to_binary",
    "osra_size": "size",
    "osra_adaptive": "adaptive",
    "osra_jaggy": "jaggy",
    "osra_unpaper": "unpaper",
    "osra_gray_threshold": "gray_threshold",
    "osra_resolution": "resolution",
    "osra_negate": "negate",
    "osra_rotate": "rotate",
    "osra_superatom_file": "superatom_config_path",
    "osra_spelling_file": "spelling_config_path",
    "verbosity": "verbosity"
}

KWARGS_OSRA_PROCESS = {
    "input_file": "input_file",
    "output": "output_file",
    "sdf_output": "output_file_sdf",
    "sdf_append": "sdf_append",
    "no_header": "write_header",
    "dry_run": "dry_run",
    "delimiter": "csv_delimiter",
    "no_use_gm": "use_gm",
    "gm_dpi": "gm_dpi",
    "no_gm_trim": "gm_trim",
    "jobs": "n_jobs",
    "input_type": "input_type",
    "no_standardize": "standardize_mols",
    "no_annotation": "annotate",
    "chemspider_token": "chemspider_token"
}

OPTS_EXTRACT = [
    click.option("--separated-output", show_default=True, is_flag=True, default=False,
                 help="Write structures taken from images and text separately. The files will have suffixes '.ocsr', '.ner' and '.opsin'. "
                      "'-o / --output' must be set."),
    click.option("--sdf-output", type=click.STRING, default="", show_default=True,
                 help="File to write SDF output in. This will write SDF file separately from OSRA and OPSIN, with '-osra.sdf' and "
                      "'-opsin.sdf' suffixes.")
]

KWARGS_EXTRACT_INIT = {
    "tessdata_path": "tessdata_path",
    "verbosity": "verbosity",
    "verbosity_classes": "verbosity_classes"
}

KWARGS_EXTRACT_PROCESS = {
    "input_file": "input_file",
    "output": "output_file",
    "sdf_output": "output_file_sdf",
    "sdf_append": "sdf_append",
    "no_header": "write_header",
    "separated_output": "separated_output",
    "input_type": "input_type",
    "lang": "lang",
    "no_use_gm": "use_gm",
    "jobs": "n_jobs",
    "opsin_types": "opsin_types",
    "no_standardize": "standardize_mols",
    "remove_duplicates": "remove_entity_duplicates",
    "delimiter": "csv_delimiter",
    "no_annotation": "annotate",
    "annotation_sleep": "annotation_sleep",
    "chemspider_token": "chemspider_token"
}

ARG_INPUT_FILE_REQUIRED = click.argument("input_file", type=click.STRING, required=True)
ARG_INPUT_FILE = click.argument("input_file", type=click.STRING, required=False)


@click.group(help="Extract chemical compounds from scientific literature. You can extract them from 2D structures or "
                  "text and use various formats of input file (images, PDF, plain text). You can also convert systematic "
                  "(IUPAC) names to linear notation (SMILES etc.).")
@click.version_option(version=__version__, prog_name="MolMiner")
def cli(**kwargs):
    pass


@cli.command(help="Use ChemSpot to extract chemical entities from document.\n"
                     "You can also send stdin.")
@add_options(OPTS_NER_INIT)
@add_options(OPTS_NER_PROCESS)
@click.option("-i", "--input-type", type=click.Choice(["pdf", "pdf_scan", "image", "text"]), show_default=True,
              help="Type of input file. If not set, MolMiner will try to determine which input type got. Only 'pdf_scan' type "
                   "cannot be determined automatically.")
@add_options(OPTS_COMMON_OCSR_NER_CONVERT)
@add_options(OPTS_COMMON_NER_EXTRACT)
@add_options(OPTS_COMMON_OCSR_NER_EXTRACT)
@add_options(OPTS_COMMON_ALL)
@ARG_INPUT_FILE
def ner(**kwargs):
    kwargs["no_standardize"] = not kwargs["no_standardize"]
    kwargs["no_convert_ions"] = not kwargs["no_convert_ions"]
    kwargs["no_header"] = not kwargs["no_header"]
    kwargs["no_normalize_text"] = not kwargs["no_normalize_text"]
    kwargs["no_annotation"] = not kwargs["no_annotation"]

    is_output_file = bool(kwargs["output"])

    stdin = click.get_text_stream("stdin")
    input_text = ""
    if not stdin.isatty():
        kwargs["input_file"] = ""
        input_text = click.get_text_stream("stdin").read().strip()
        if not input_text and not kwargs["input_file"]:
            raise click.UsageError("Cannot perform NER: stdin is empty and input file is not provided.")

    kwargs["opsin_types"] = get_opsin_types(kwargs["opsin_types"])

    init_kwargs = get_kwargs(kwargs, KWARGS_CHS_INIT)
    process_kwargs = get_kwargs(kwargs, KWARGS_CHS_PROCESS)

    chemspot = ChemSpot(**init_kwargs)
    result = chemspot.process(input_text=input_text, **process_kwargs)

    if kwargs["dry_run"]:
        print(result)
        exit(0)

    if kwargs["raw_output"]:
        print(result["stdout"])
        eprint(result["stderr"])
        exit(0)

    if not is_output_file:
        print(dict_to_csv(result["content"], csv_delimiter=kwargs["delimiter"], write_header=kwargs["no_header"]))


@cli.command(help="Use OSRA to extract 2D structures from document.")
@add_options(OPTS_OCSR_INIT)
@add_options(OPTS_OCSR_PROCESS)
@click.option("-i", "--input-type", type=click.Choice(["pdf", "image"]), show_default=True,
              help="Type of input file. If not set, MolMiner will try to determine which input type got.")
@add_options(OPTS_COMMON_OCSR_NER_CONVERT)
@add_options(OPTS_COMMON_OCSR_CONVERT_EXTRACT)
@add_options(OPTS_COMMON_OCSR_CONVERT)
@add_options(OPTS_COMMON_OCSR_EXTRACT)
@add_options(OPTS_COMMON_OCSR_NER_EXTRACT)
@add_options(OPTS_COMMON_ALL)
@ARG_INPUT_FILE_REQUIRED
def ocsr(**kwargs):
    kwargs["no_header"] = not kwargs["no_header"]
    kwargs["no_use_gm"] = not kwargs["no_use_gm"]
    kwargs["no_gm_trim"] = not kwargs["no_gm_trim"]
    kwargs["no_standardize"] = not kwargs["no_standardize"]
    kwargs["no_annotation"] = not kwargs["no_annotation"]

    is_output_file = bool(kwargs["output"])

    init_kwargs = get_kwargs(kwargs, KWARGS_OSRA_INIT)
    process_kwargs = get_kwargs(kwargs, KWARGS_OSRA_PROCESS)

    osra = OSRA(**init_kwargs)
    result = osra.process(output_formats=["smiles", "inchi", "inchikey"], **process_kwargs)

    if kwargs["dry_run"]:
        print(result)
        exit(0)

    if kwargs["raw_output"]:
        print(result["stdout"])
        eprint(result["stderr"])
        exit(0)

    if not is_output_file:
        print(dict_to_csv(result["content"], csv_delimiter=kwargs["delimiter"], write_header=kwargs["no_header"]))

@cli.command(help="Use OPSIN to convert IUPAC names to linear notation (SMILES etc.). One name per line in input file.\n"
                  "You can also send stdin.")
@add_options(OPTS_CONVERT_INIT)
@add_options(OPTS_CONVERT_PROCESS)
@add_options(OPTS_COMMON_OCSR_CONVERT)
@add_options(OPTS_COMMON_OCSR_CONVERT_EXTRACT)
@add_options(OPTS_COMMON_OCSR_NER_CONVERT)
@add_options(OPTS_COMMON_ALL)
@ARG_INPUT_FILE
def convert(**kwargs):
    kwargs["no_header"] = not kwargs["no_header"]
    kwargs["no_normalize_plurals"] = not kwargs["no_normalize_plurals"]
    kwargs["no_standardize"] = not kwargs["no_standardize"]
    kwargs["opsin_no_allow_acids_without_acid"] = not kwargs["opsin_no_allow_acids_without_acid"]
    kwargs["opsin_no_detailed_failure_analysis"] = not kwargs["opsin_no_detailed_failure_analysis"]
    kwargs["opsin_no_allow_radicals"] = not kwargs["opsin_no_allow_radicals"]
    kwargs["opsin_no_allow_uninterpretable_stereo"] = not kwargs["opsin_no_allow_uninterpretable_stereo"]

    is_output_file = bool(kwargs["output"])

    stdin = click.get_text_stream("stdin")
    input_text = ""
    if not stdin.isatty():
        kwargs["input_file"] = ""
        input_text = click.get_text_stream("stdin").read().strip()
    if not input_text and not kwargs["input_file"]:
        raise click.UsageError("Cannot do conversion: stdin is empty and input file is not provided.")

    init_kwargs = get_kwargs(kwargs, KWARGS_OPSIN_INIT)
    process_kwargs = get_kwargs(kwargs, KWARGS_OPSIN_PROCESS)

    opsin = OPSIN(**init_kwargs)
    result = opsin.process(input=input_text, output_formats=["smiles", "inchi", "inchikey"], **process_kwargs)

    if kwargs["dry_run"]:
        print(result)
        exit(0)

    if kwargs["raw_output"]:
        print(result["stdout"])
        eprint(result["stderr"])
        exit(0)

    if not is_output_file:
        print(dict_to_csv(result["content"], csv_delimiter=kwargs["delimiter"], write_header=kwargs["no_header"]))


@cli.command(help="Combine OSRA, ChemSpot and OPSIN to extract chemical compounds from document.")
@add_options(OPTS_EXTRACT)
@click.option("-i", "--input-type", type=click.Choice(["pdf", "pdf_scan", "image"]), show_default=True,
              help="Type of input file. If not set, MolMiner will try to determine which input type got. Only 'pdf_scan' type "
              "cannot be determined automatically.")
@add_options(OPTS_NER_INIT)
@add_options(OPTS_OCSR_INIT)
@add_options(OPTS_CONVERT_INIT)
@add_options(OPTS_COMMON_OCSR_EXTRACT)
@add_options(OPTS_COMMON_OCSR_CONVERT_EXTRACT)
@add_options(OPTS_COMMON_NER_EXTRACT)
@add_options(OPTS_COMMON_OCSR_NER_EXTRACT)
@add_options(OPTS_COMMON_ALL)
@ARG_INPUT_FILE_REQUIRED
def extract(**kwargs):
    kwargs["no_header"] = not kwargs["no_header"]
    kwargs["no_use_gm"] = not kwargs["no_use_gm"]
    kwargs["no_standardize"] = not kwargs["no_standardize"]
    kwargs["opsin_no_allow_acids_without_acid"] = not kwargs["opsin_no_allow_acids_without_acid"]
    kwargs["opsin_no_detailed_failure_analysis"] = not kwargs["opsin_no_detailed_failure_analysis"]
    kwargs["opsin_no_allow_radicals"] = not kwargs["opsin_no_allow_radicals"]
    kwargs["opsin_no_allow_uninterpretable_stereo"] = not kwargs["opsin_no_allow_uninterpretable_stereo"]
    kwargs["no_annotation"] = not kwargs["no_annotation"]

    kwargs["opsin_types"] = get_opsin_types(kwargs["opsin_types"])

    is_output_file = bool(kwargs["output"])

    ner_init_kwargs = get_kwargs(kwargs, KWARGS_CHS_INIT)
    ocsr_init_kwargs = get_kwargs(kwargs, KWARGS_OSRA_INIT)
    convert_init_kwargs = get_kwargs(kwargs, KWARGS_OPSIN_INIT)
    extract_init_kwargs = get_kwargs(kwargs, KWARGS_EXTRACT_INIT)
    extract_process_kwargs = get_kwargs(kwargs, KWARGS_EXTRACT_PROCESS)

    extract_init_kwargs["verbosity_classes"] = extract_init_kwargs["verbosity"]

    extractor = Extractor(chemspot_options=ner_init_kwargs, osra_options=ocsr_init_kwargs, opsin_options=convert_init_kwargs,
                          **extract_init_kwargs)
    result = extractor.process(**extract_process_kwargs)

    if not is_output_file:
        print(dict_to_csv(result, csv_delimiter=kwargs["delimiter"], write_header=kwargs["no_header"]))


def get_opsin_types(types):
    valid_opsin_types = ["SYSTEMATIC", "IDENTIFIER", "FORMULA", "TRIVIAL", "ABBREVIATION", "FAMILY", "MULTIPLE"]
    opsin_types = [_.upper() for _ in types.split(",")]
    opsin_types = [_ for _ in opsin_types if _ in valid_opsin_types]

    if not opsin_types:
        opsin_types = ["SYSTEMATIC"]

    return opsin_types

if __name__ == "__main__":
    cli()
