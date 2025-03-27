from django.core.management.base import BaseCommand

from slots.utils import create_time_slots


class Command(BaseCommand):
    help = "KST 기준으로 30분 간격의 슬롯을 생성합니다."

    def add_arguments(self, parser):
        parser.add_argument(
            "--start_date", type=str, help="시작 날짜 (YYYY-MM-DD 형식)"
        )
        parser.add_argument("--end_date", type=str, help="종료 날짜 (YYYY-MM-DD 형식)")
        parser.add_argument(
            "--days", type=int, default=30, help="생성할 일수 (기본값: 30일)"
        )

    def handle(self, *args, **options):
        self.stdout.write(f"슬롯 생성 중...")

        # 유틸리티 함수 사용
        slot_count, slots = create_time_slots(
            start_date=options["start_date"],
            end_date=options["end_date"],
            days=options["days"],
        )

        # 처음, 끝 슬롯 시간 출력
        self.stdout.write(f"처음 슬롯 시간: {slots[0].slot_start_time}")
        self.stdout.write(f"끝 슬롯 시간: {slots[-1].slot_end_time}")

        self.stdout.write(
            self.style.SUCCESS(f"{slot_count}개의 슬롯이 성공적으로 생성되었습니다.")
        )
