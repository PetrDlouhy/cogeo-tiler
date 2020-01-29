"""Setup cogeo-tiler"""

from setuptools import setup, find_packages

# Runtime requirements.
inst_reqs = ["lambda-proxy~=5.0", "rio-tiler~=1.3", "rio-color"]

extra_reqs = {
    "test": ["mock", "pytest", "pytest-cov"],
    "dev": ["mock", "pytest", "pytest-cov", "pre-commit"],
}

setup(
    name="cogeo-tiler",
    version="0.0.1",
    description=u"Create and serve Map tile from Cloud Optimized GeoTIFF.",
    long_description=u"Create and serve Map tile from Cloud Optimized GeoTIFF.",
    python_requires=">=3",
    classifiers=[
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
    ],
    keywords="COG COGEO Mosaic GIS",
    author=u"Vincent Sarago",
    author_email="vincent@developmentseed.org",
    url="https://github.com/developmentseed/cogeo-tiler",
    license="BSD",
    packages=find_packages(exclude=["ez_setup", "examples", "tests"]),
    include_package_data=True,
    zip_safe=False,
    install_requires=inst_reqs,
    extras_require=extra_reqs,
    entry_points={"console_scripts": ["cogeo-tiler = cogeo_tiler.scripts.cli:run"]},
)
