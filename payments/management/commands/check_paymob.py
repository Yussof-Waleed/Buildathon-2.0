from django.core.management.base import BaseCommand

from payments.paymob_config import get_paymob_readiness


class Command(BaseCommand):
    help = 'Check Paymob configuration readiness for checkout and webhooks.'

    def handle(self, *args, **options):
        readiness = get_paymob_readiness()

        if readiness['ready']:
            self.stdout.write(self.style.SUCCESS('Paymob: ready'))
        else:
            self.stdout.write(self.style.WARNING('Paymob: not ready'))

        if readiness['missing']:
            self.stdout.write('Missing:')
            for key in readiness['missing']:
                self.stdout.write(f'  - {key}')

        if readiness['warnings']:
            self.stdout.write('Warnings:')
            for warning in readiness['warnings']:
                self.stdout.write(f'  - {warning}')

        self.stdout.write(f'ready: {readiness["ready"]}')
