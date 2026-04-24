from setuptools import setup, find_packages

setup(
    name="shxrkcleaner",
    version="1.0.0",
    packages=find_packages(),
    entry_points={
        "console_scripts": [
            "shxrkcleaner=cleaner.cli:main",
        ],
    },
    python_requires=">=3.8",
)
