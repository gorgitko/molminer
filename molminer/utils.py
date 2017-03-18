import magic

import sys
from collections import namedtuple
import subprocess
from typing import Union
from tempfile import TemporaryDirectory
from typing import Union
import os
from glob import glob
import csv
from io import StringIO
import re


Output = namedtuple("Output", ["stdout", "stderr", "exit_code"])


def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


def common_subprocess(commands: Union[list, str], stdin: str = "", stdin_encoding: str = "utf-8") -> namedtuple:
    """
    Return the namedtuple with stdout, stderr and exit code from shell command.

    Parameters
    ----------
    commands : list or str
        List of commands to execute in shell, e.g. ["ls", "-a"]. If string is given, split it to list.
    stdin : str
        Stdin to send to shell.
    stdin_encoding : str

    Returns
    -------
    namedtuple
        Fields: "stdout", "stderr", "exit_code"
    """

    if isinstance(commands, str):
        commands = commands.split()

    p = subprocess.Popen(commands, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
    if stdin:
        stdout, stderr = p.communicate(input=bytes(stdin, encoding=stdin_encoding))
    else:
        stdout, stderr = p.communicate()
    p.wait()
    stdout = stdout.decode()
    stderr = stderr.decode()
    return Output(stdout=stdout, stderr=stderr, exit_code=p.returncode)


def get_text_from_pdf(input_file: str) -> str:
    """
    Get embedded text from PDF using pdftotext binary (part of poppler-utils).

    Parameters
    ----------
    input_file : str

    Returns
    -------
    str
    """

    text, stderr, exit_code = common_subprocess(["pdftotext", input_file, "-"])
    if exit_code > 0:
        raise RuntimeError("Error when extracting embedded text from PDF with pdftotext. Stderr: {}".format(stderr))
    return text


def get_text_from_pdf_scan(input_file: str,
                           lang: str = "eng",
                           tessdata_prefix: str = "",
                           tesseract_engine: int = 2,
                           as_page_list: bool = False)-> Union[str, TemporaryDirectory]:
    """
    Get text from PDF which consists of scanned pages (images). First convert PDF to PNG images (one image per page) and
    then apply Tesseract OCR to get text.

    Parameters
    ----------
    input_file : str
    lang : str
        | Language which will Tesseract use for OCR. Available languages: https://github.com/tesseract-ocr/tessdata
        | Multiple languages can be specified with "+" character, e.g. "eng+bul+fra".
        | Language data files must be stored in directory defined in TESSDATA_PREFIX environmental variable.
    tessdata_prefix : str
        Path to directory with Tesseract language data. If empty, the TESSDATA_PREFIX environment variable will be used.
    tesseract_engine : int
        OCR Engine modes:

            | 0    Original Tesseract only.
            | 1    Neural nets LSTM only.
            | 2    Tesseract + LSTM.
            | 3    Default, based on what is available.
    as_page_list : bool
        If True, return list of text of individual pages.

    Returns
    -------
    (str, TemporaryDirectory)
        | Text and TemporaryDirectory object, which contains name of temporary directory with converted images.
        | This directory will be deleted when script exits, when TemporaryDirectory object is deleted or its method cleanup() is called.
    """

    if tessdata_prefix:
        tessdata_prefix = "--tessdata-dir {}".format(tessdata_prefix)

    if not 0 <= tesseract_engine <= 3:
        raise ValueError("Invalid 'tesseract_engine' value. Possible values: 0, 1, 2, 3")

    input_file_path = os.path.abspath(input_file)
    input_file = os.path.basename(input_file)

    temp_dir = TemporaryDirectory()
    convert_cmd = "gm convert -density 300 {input_file_path} +adjoin -depth 8 -quality 100 {temp_dir}/{input_file}-0%d.png".format(
        input_file_path=input_file_path, input_file=input_file, temp_dir=temp_dir.name)
    stdout, stderr, exit_code = common_subprocess(convert_cmd.split())
    if exit_code > 0:
        raise RuntimeError("Error converting scanned PDF to image. Stderr: {}".format(stderr))

    text = ""
    pages = []
    ocr_cmd = "tesseract {{image_file}} stdout -l {lang} --oem 2 {tessdata_prefix}".format(
        lang=lang, tessdata_prefix=tessdata_prefix)

    for file, page in get_temp_images(temp_dir.name):
        _text, stderr, exit_code = common_subprocess(ocr_cmd.format(image_file=file).split())
        if exit_code > 0:
            raise RuntimeError("Tesseract OCR error. Stderr: {}".format(stderr))
        if as_page_list:
            pages.append(_text)
        else:
            text += "\f" + _text

    return pages, temp_dir if as_page_list else text, temp_dir


def get_text_from_image(input_file: str,
                        lang: str = "eng",
                        tessdata_prefix: str = "") -> str:
    """
    Get text from image using Tesseract OCR.

    Parameters
    ----------
    input_file : str
    lang : str
        | Language which will Tesseract use for OCR. Available languages: https://github.com/tesseract-ocr/tessdata
        | Multiple languages can be specified with "+" character, i.e. "eng+bul+fra".
    tessdata_prefix : str
        Path to directory with Tesseract language data. If empty, the TESSDATA_PREFIX environment variable will be used.

    Returns
    -------
    str
    """

    if tessdata_prefix:
        tessdata_prefix = "--tessdata-dir {}".format(tessdata_prefix)

    ocr_cmd = "tesseract {input_file} stdout -l {lang} {tessdata_prefix}".format(
        input_file=input_file, lang=lang, tessdata_prefix=tessdata_prefix)
    text, stderr, exit_code = common_subprocess(ocr_cmd.split())
    if exit_code > 0:
        raise RuntimeError("Tesseract OCR error. Stderr: {}".format(stderr))
    return text


def get_input_file_type(input_file: str) -> str:
    mime_type = magic.from_file(input_file, mime=True)
    input_type = mime_type.split("/")

    if input_type[1] == "pdf":
        return "pdf"
    elif input_type[0] == "image":
        return "image"
    elif input_type[0] == "text":
        return "text"
    else:
        return mime_type


def get_text(input_file: str, input_type: str, lang: str = "en", tessdata_prefix: str = "") -> str:
    if input_type == "pdf":
        return get_text_from_pdf(input_file), None
    elif input_type == "pdf_scan":
        return get_text_from_pdf_scan(input_file, lang=lang, tessdata_prefix=tessdata_prefix)
    elif input_type == "image":
        return get_text_from_image(input_file, lang=lang, tessdata_prefix=tessdata_prefix), None
    else:
        raise ValueError("Unknown 'input_type': {}".format(input_type))


def dict_to_csv(dicts: list, output_file: str = "", csv_delimiter: str = ";", write_header: bool = True):
    if output_file:
        output = open(output_file, mode="w", encoding="utf-8")
    else:
        output = StringIO()

    if not dicts:
        if output_file:
            write_empty_file(output_file)
            return
        else:
            return ""

    w = csv.DictWriter(output, dicts[0].keys(), delimiter=csv_delimiter)
    if write_header:
        w.writeheader()
    w.writerows(dicts)

    if not output_file:
        contents = output.getvalue()
        output.close()
        return contents
    else:
        output.flush()
        output.close()


def write_empty_file(file: str, csv_delimiter: str = ";", header: list = None, write_header: bool = False):
    with open(file, mode="w", encoding="utf-8") as f:
        if header and write_header:
            f.write(csv_delimiter.join(header))
        f.write("")


def get_temp_images(temp_dir):
    r = re.compile(r"(\d+)\.png$", flags=re.IGNORECASE)
    return sorted(
        [(file, int(r.findall(file)[0]) + 1) for file in glob("{}/*".format(temp_dir))], key=lambda x: x[1])


def pdf_to_images(input_file_path, output_dir,
                  gm_command="gm convert -density {dpi} {input_file_path} +adjoin {trim} -quality 100 {temp_dir}/{input_file}-%d.png",
                  dpi=300, trim=True):
    trim = "-trim" if trim else ""
    stdout, stderr, exit_code = common_subprocess(
        gm_command.format(dpi=dpi, trim=trim, input_file_path=input_file_path,
                          input_file=os.path.basename(input_file_path), temp_dir=output_dir))

    if exit_code > 0:
        raise RuntimeError("Error when converting PDF to PNG images. Stderr: {}".format(stderr))

    return stdout, stderr, exit_code
