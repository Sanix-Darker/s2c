# NOTE: Make sure to update version number
# pip install twine wheel
# We remove unecessary files/folders
rm -rf build/*
rm -rf dist/*
rm -rf *-info

python3 setup.py sdist bdist_wheel
python3 -m twine upload dist/*
