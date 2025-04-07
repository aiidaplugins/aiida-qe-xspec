"""Command line interface for the aiida-qe-xspec package.
"""

from aiida import load_profile
import click


@click.group()
def cli():
    pass


@cli.command(help='Import the PAW pseudopotentials into the AiiDA database.')
def setup_pseudos():
    from aiida_qe_xspec.utils import install_xps_pseudos

    load_profile()
    install_xps_pseudos()


@cli.command(
    help='Set up core-hole pseudo-potential'
)
def post_install():
    from aiida_qe_xspec.utils import install_xps_pseudos

    load_profile()
    install_xps_pseudos()


if __name__ == '__main__':
    cli()
