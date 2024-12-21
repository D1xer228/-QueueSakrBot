def map_lesson_name_to_subject(lesson_name: str) -> str:
  return {
    'ПОКС': 'Программное обеспечение компьютерных сетей',
    'АСОС': 'Администрирование сетевых операционных систем',
    'ОАП': 'Основы алгоритмизации и программирования'
  }[lesson_name]
