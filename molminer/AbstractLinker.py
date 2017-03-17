from abc import ABC, abstractmethod
from collections import namedtuple


class AbstractLinker(ABC):
    """
    Act as a linker between Python and command-line interface of various SW.

    Attributes
    ----------
    _OPTIONS_REAL : dict
        Internal dict which maps the passed options to real SW command-line arguments.
    options : dict
        Dict of SW's command-line parameters.
    options_internal : dict
        Dict of internal options.

    Methods
    -------
    process()
        Process the input file with SW.
    build_commands(options, _OPTIONS_REAL, path_to_sw)
        Convert the internal parameters to real SW's command-line parameters.
    help()
        Return SW's help.
    """

    @staticmethod
    def build_commands(options: dict, options_real: dict, path_to_sw: str) -> list:
        """
        Convert the internal parameters to real SW's command-line parameters.

        Parameters
        ----------
        options : dict
            Options to build commands from.
        options_real : dict
            Dict which maps internal parameters to real SW's ones.
        path_to_sw : str
            Path to SW's binary.

        Returns
        -------
        (list, dict, dict)
            List of commands for calling the subprocess, dict of parameters, dict of internal parameters.
        """

        _options = {}
        _options_internal = {}

        commands = [path_to_sw]

        for k, v in options.items():
            if k in options_real and v:
                option = options_real[k]
                if option[1]:
                    commands.append(option[0])
                    commands.append(option[1].format(v))
                else:
                    commands.append(option[0])
                _options[option[0]] = v
                _options_internal[k] = v

        return commands, _options, _options_internal

    @abstractmethod
    def set_options(self, options: dict):
        """
        Sets the options passed in dict. Keys are the same as optional parameters in child's constructor.

        Parameters
        ----------
        options
            Dict of new options.
        """

        pass

    @abstractmethod
    def help(self) -> str:
        """
        Returns
        -------
        str
            SW's help message.
        """

        pass

    @abstractmethod
    def process(self, **kwargs) -> namedtuple:
        """
        Process the input with given SW.

        Parameters
        ----------
        kwargs

        Returns
        -------
        OrderedDict
        """

        pass
