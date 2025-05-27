# setup.py
from setuptools import setup, find_packages

setup(
  name="nurse_talk_app",
  version="0.1",
  package_dir={"": "src"},
  packages=find_packages("src"),
)
