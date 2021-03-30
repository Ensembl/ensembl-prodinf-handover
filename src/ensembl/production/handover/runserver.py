import logging.config
import click
from ensembl.production.handover.app.main import app

@click.command()
@click.option('-p', '--port', type=int, default=5000)
def main(port):
    logging.info('>>>>> Starting development server at http://{}/handover/ <<<<<'.format('localhost'))
    app.run(debug=True, port=port, host='0.0.0.0')