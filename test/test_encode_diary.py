import unittest
from pathlib import Path
import paperstream.encode_diary as encode
from shutil import copyfile

class TestEncodeDiary(unittest.TestCase):
    
    def setUp(self):
        encode.EXTRACTED_PAGES_DIR = Path("test/output/temporal/diary_pages/")
        encode.EXTRACTED_AREAS_DIR = Path("test/output/temporal/answers_areas/")
        encode.EXTRACTED_MARK_DIR = Path("test/output/temporal/mark_areas/")
        encode.ENCODED_DIARIES_DIR = Path("test/output/")
        self.TEMPLATE_DIR = Path("test/input/template/")
        self.RUBRIC = "0,hour,12,78.99300699,176.9956522,12\n0,hour,1,111.98601399,183.9956522,12\n0,hour,2,132,208.0065217,12\n0,hour,3,141.9895105,235.9978261,12\n0,hour,4,132.986014,268.9956522,12\n0,hour,5,112.9895105,291.0065217,12\n0,hour,6,79.99300699,299.9978261,12\n0,hour,7,47.98951049,290,12\n0,hour,8,27.98251748,268.9586957,12\n0,hour,9,19.982517483,237.9913043,12\n0,hour,10,27.9965035,207.9891304,12\n0,hour,11,46.98951049,184.9695652,12\n0,ampm,am,79.99300699,218.9913043,12\n0,ampm,pm,78.98951049,257.9913043,12\n0,minute,0,179.9895105,176.9934783,12\n0,minute,15,180.993007,217.9956522,12\n0,minute,30,179.993007,258.9956522,12\n0,minute,45,180.9895105,300.9956522,12\n0,symptom1,0,369.993007,163.9956522,12\n0,symptom1,1,408.9895105,163.9956522,12\n0,symptom1,2,446.9895105,163.9934783,12\n0,symptom1,3,485.993007,164.9978261,12\n0,symptom2,3,486.9895105,225.9978261,12\n0,symptom2,2,447.9895105,224.9978261,12\n0,symptom2,1,407.9895105,224.9978261,12\n0,symptom2,0,369.993007,224.9978261,12\n0,symptom3,0,370.9895105,287.9978261,12\n0,symptom3,1,408.993007,287.9956522,12\n0,symptom3,2,446.993007,288.9934783,12\n0,symptom3,3,486.9895105,288.9956522,12\n1,hour,12,79.98951049,465.5652174,12\n1,hour,1,112.9825175,472.5652174,12\n1,hour,2,132.99650350000002,496.576087,12\n1,hour,3,142.986014,524.5673913,12\n1,hour,4,133.9825175,557.5652174,12\n1,hour,5,113.986014,579.576087,12\n1,hour,6,80.98951049,588.5673913,12\n1,hour,7,48.98601399,578.5695652,12\n1,hour,8,28.97902098,557.5282609,12\n1,hour,9,20.979020978999998,526.5608696,12\n1,hour,10,28.99300699,496.5586957,12\n1,hour,11,47.98601399,473.5391304,12\n1,ampm,am,80.98951049,507.5608696,12\n1,ampm,pm,79.98601399,546.5608696,12\n1,minute,0,180.986014,465.5630435,12\n1,minute,15,181.9895105,506.5652174,12\n1,minute,30,180.9895105,547.5652174,12\n1,minute,45,181.986014,589.5652174,12\n1,symptom1,0,370.9895105,452.5652174,12\n1,symptom1,1,409.986014,452.5652174,12\n1,symptom1,2,447.986014,452.5630435,12\n1,symptom1,3,486.9895105,453.5673913,12\n1,symptom2,3,487.986014,514.5673913,12\n1,symptom2,2,448.986014,513.5673913,12\n1,symptom2,1,408.986014,513.5673913,12\n1,symptom2,0,370.9895105,513.5673913,12\n1,symptom3,0,371.986014,576.5673913,12\n1,symptom3,1,409.9895105,576.5652174,12\n1,symptom3,2,447.9895105,577.5630435,12\n1,symptom3,3,487.986014,577.5652174,12\n2,hour,12,79.98951049,689.0782609,12\n2,hour,1,112.9825175,696.0782609,12\n2,hour,2,132.99650350000002,720.0891304,12\n2,hour,3,142.986014,748.0804348,12\n2,hour,4,133.9825175,781.0782609,12\n2,hour,5,113.986014,803.0891304,12\n2,hour,6,80.98951049,812.0804348,12\n2,hour,7,48.98601399,802.0826087,12\n2,hour,8,28.97902098,781.0413043,12\n2,hour,9,20.979020978999998,750.073913,12\n2,hour,10,28.99300699,720.0717391,12\n2,hour,11,47.98601399,697.0521739,12\n2,ampm,am,80.98951049,731.073913,12\n2,ampm,pm,79.98601399,770.073913,12\n2,minute,0,180.986014,689.076087,12\n2,minute,15,181.9895105,730.0782609,12\n2,minute,30,180.9895105,771.0782609,12\n2,minute,45,181.986014,813.0782609,12\n2,symptom1,0,370.9895105,676.0782609,12\n2,symptom1,1,409.986014,676.0782609,12\n2,symptom1,2,447.986014,676.076087,12\n2,symptom1,3,486.9895105,677.0804348,12\n2,symptom2,3,487.986014,738.0804348,12\n2,symptom2,2,448.986014,737.0804348,12\n2,symptom2,1,408.986014,737.0804348,12\n2,symptom2,0,370.9895105,737.0804348,12\n2,symptom3,0,371.986014,800.0804348,12\n2,symptom3,1,409.9895105,800.0782609,12\n2,symptom3,2,447.9895105,801.076087,12\n2,symptom3,3,487.986014,801.0782609,12"

    def test_encode_diary_png(self):
        answers = encode.encode_diary("test/input/test_diary_png.zip", self.TEMPLATE_DIR, self.RUBRIC, "01/09/2018")
        test_answers = Path("test/comparison_files/test_diary_png.csv")
        self.assertTrue(answers.stat().st_size == test_answers.stat().st_size)

    def test_encode_diary_tif(self):
        answers = encode.encode_diary("test/input/test_diary_tif.tif", self.TEMPLATE_DIR, self.RUBRIC, "01/09/2018")
        test_answers = Path("test/comparison_files/test_diary_tif.csv")
        self.assertTrue(answers.stat().st_size == test_answers.stat().st_size)
        

if __name__ == '__main__':
    unittest.main()