import click
"""
https://click.palletsprojects.com/en/stable/quickstart/
"""

@click.group()
def cli():
    pass

@click.command()
def initdb():
    click.echo('Initialized the database')

@click.command()
def dropdb():
    click.echo('Dropped the database')

@click.command()
@click.option('--count', default=1, help='Number of greetings.')
@click.argument('name')
def hello(count, name):
    """Simple program that greets NAME for a total of COUNT times."""
    for x in range(count):
        click.echo(f"Hello {name}!")

cli.add_command(initdb)
cli.add_command(dropdb)
cli.add_command(hello)


if __name__ == '__main__':
    cli()