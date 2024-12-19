from setuptools import setup, find_packages

setup(
    name='odoo_python_api_wrapper',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'keepassxc-proxy-client'
    ],
    url='https://github.com/YonasJ/odoo-python-api-wrapper',
    author='Yonas Jongkind',
    author_email='yonas.jongkind@gmail.com',
    description='Wrapper for CRUD operations of Odoo objects via the API, including generating wrapper objects for Odoo models',
)