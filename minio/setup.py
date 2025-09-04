# MinIO集成包
# 独立的MinIO功能模块，提供完整的对象存储集成解决方案

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="toklabel-minio",
    version="1.0.0",
    author="TOKLABEL Team",
    author_email="team@toklabel.org",
    description="MinIO集成模块，为TOKLABEL项目提供对象存储支持",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/toklabel/toklabel-minio",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Information Analysis",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "minio>=7.1.0",
        "fastapi>=0.68.0",
        "uvicorn>=0.15.0",
        "python-multipart>=0.0.5",
        "click>=8.0.0",
        "aiohttp>=3.8.0",
        "pyyaml>=6.0",
        "pandas>=1.3.0",
        "redis>=4.0.0",
        "requests>=2.25.0",
        "label-studio-sdk>=0.0.40",
        "numpy>=1.21.0",
        "python-dotenv>=0.19.0",
    ],
    extras_require={
        "dev": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "black>=21.0",
            "flake8>=3.8",
            "mypy>=0.800",
        ],
        "test": [
            "pytest>=6.0",
            "pytest-cov>=2.0",
            "pytest-mock>=3.6",
        ],
    },
    entry_points={
        "console_scripts": [
            "minio-cli=minio.cli.minio_cli:cli",
        ],
    },
    include_package_data=True,
    package_data={
        "minio": ["*.yaml", "*.yml", "*.json"],
    },
)
