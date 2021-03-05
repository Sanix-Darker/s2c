import setuptools
from s2c.settings import version as VERSION


with open("README.md", "r") as fh:
    long_description = fh.read()

with open('requirements.txt') as f:
    required = f.read().splitlines()


setuptools.setup(
    name="s2c",
    version=VERSION,
    install_requires=required,
    scripts=['./scripts/s2c', './scripts/s2c_server'],
    author="Sanix-darker",
    author_email="s4nixd@gmail.com",
    description="A Video + Audio Chat in your terminal !",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sanix-darker/s2c",
    packages=setuptools.find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)

