#!/usr/bin/env python3
"""
IVAS Python SDK 安装配置文件
"""

from setuptools import setup, find_packages
import os

# 读取 README 文件
readme_path = os.path.join(os.path.dirname(__file__), 'README.md')
if os.path.exists(readme_path):
    with open(readme_path, 'r', encoding='utf-8') as f:
        long_description = f.read()
else:
    long_description = 'IVAS 无人机客户端 SDK'

setup(
    name='ivas',
    version='1.0.0',
    author='IVAS Team',
    author_email='ivas@example.com',
    description='IVAS 无人机客户端 SDK - 提供与 IVAS 服务器交互的接口',
    long_description=long_description,
    long_description_content_type='text/markdown',
    url='https://github.com/your-org/ivas',
    packages=find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Programming Language :: Python :: 3.13',
    ],
    python_requires='>=3.7',
    install_requires=[
        'requests>=2.25.0',
    ],
    extras_require={
        'dev': [
            'pytest>=6.0',
            'pytest-cov>=2.0',
        ],
    },
    keywords='ivas drone client sdk api',
    project_urls={
        'Bug Reports': 'https://github.com/your-org/ivas/issues',
        'Source': 'https://github.com/your-org/ivas',
    },
)
