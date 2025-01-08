from setuptools import setup, find_packages

setup(
    name="spectral_analyzer",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "paramiko>=2.7.2",
        "matplotlib>=3.3.0"
    ]
)