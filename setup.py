from setuptools import setup, find_packages

setup(
    name="jpl3",
    version="0.1.2",
    description="JEMViewer3 Python Library for recording matplotlib commands",
    author="SCE2",
    packages=find_packages(),
    install_requires=[
        "matplotlib",
        "numpy",
        "pandas",
    ],
    python_requires=">=3.9",
)