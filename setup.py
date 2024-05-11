"""``geoh5vista``: 3D visualization for the geoh5 format.
"""
import setuptools

__version__ = "0.0.1"

with open("README.md", "r") as f:
    long_description = f.read()

setuptools.setup(
    name="geoh5vista",
    version=__version__,
    author="Derek Kinakin",
    author_email="",
    description="3D visualization for the geoh5 format.",
    long_description=long_description,
    long_description_content_type="text/x-rst",
    url="https://github.com/derek-kinakin/geoh5vista",
    packages=setuptools.find_packages(),
    install_requires=[
        "geoh5py>=0.8.0",
        "pyvista>=0.43",
    ],
    classifiers=(
        "Programming Language :: Python",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Natural Language :: English",
    ),
)
