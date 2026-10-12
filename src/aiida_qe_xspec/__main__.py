"""Command line interface for the aiida-qe-xspec package."""

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


@cli.command(help='Set up core-hole pseudo-potential')
def post_install():
    from aiida_qe_xspec.utils import download_data, install_xps_pseudos, install_xas_pseudos

    load_profile()
    download_data()
    install_xps_pseudos()
    install_xas_pseudos()


@cli.command(help='Verify downloaded data and imported pseudopotentials.')
@click.option('-p', '--profile', default='default', help='AiiDA profile name.')
def verify_post_install(profile):
    from aiida_qe_xspec.utils import verify_setup

    load_profile(profile)
    try:
        verify_setup()
    except (OSError, RuntimeError, ValueError) as error:
        raise click.ClickException(str(error)) from error
    click.echo('XSpec post-install setup is valid.')


if __name__ == '__main__':
    cli()
