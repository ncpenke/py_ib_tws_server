import distutils.cmd
from setuptools import setup, find_packages
import setuptools.command.build_py
import ib_tws_server.codegen.main
import os.path

class CodegenCommand(distutils.cmd.Command):
    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        dir = os.path.dirname(os.path.realpath(__file__))
        dir = os.path.join(dir, "ib_tws_server", "gen")
        ib_tws_server.codegen.main.generate(dir)
        setuptools.command.build_py.build_py.run(self)

class BuildPyCommand(setuptools.command.build_py.build_py):
    def run(self):
        self.run_command('codegen')
        setuptools.command.build_py.build_py.run(self)

setup(name='ib_tws_server',
    version='0.0',
    description='Interactive Brokers TWS Server',
    author='Chandra Penke',
    url='https://github.com/ncpenke/py_ib_tws_server',
    cmdclass={
        'codegen': CodegenCommand,
        'build_py': BuildPyCommand
    }
)
