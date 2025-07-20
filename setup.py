from setuptools import setup, find_packages

setup(
    name='odoo_python_api_wrapper',
    version='0.1.0',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'keepassxc-proxy-client'
    ],
    python_requires='>=3.8',
    url='https://github.com/YonasJ/odoo-python-api-wrapper',
    author='Yonas Jongkind',
    author_email='yonas.jongkind@gmail.com',
    description='Wrapper for CRUD operations of Odoo objects via the API, including generating wrapper objects for Odoo models',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    classifiers=[
        'Programming Language :: Python :: 3',
        'License :: OSI Approved :: MIT License',
        'Operating System :: OS Independent',
    ],
)