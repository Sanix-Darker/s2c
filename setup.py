from setuptools import setup

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="s2c",
    version="0.0.7",
    author="Sanix-Darker",
    author_email="s4nixd@gmail.com",
    description="A Video + Audio Chat in your terminal!",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sanix-darker/s2c",
    python_requires=">=3.10",
)
