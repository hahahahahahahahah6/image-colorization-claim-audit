import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from image_colorization_claim_audit import phrases
from image_colorization_claim_audit.audit import audit, claims, evidence, main

COLORIZATION = ['image colorization', 'image-colorization', 'imagecolorization', 'image colorization model', 'image colorization models', 'image colorization system', 'image colorization systems', 'image colorization feature', 'image colorization capability', 'image colorization support', 'supports image colorization', 'image colorization tool', 'image colorization api', 'image colorization pipeline', 'image colorization algorithm', 'image colorization library', 'image colorization framework', 'image colorization service', 'image colorization function', 'image colorization engine', 'image colorization engines', 'image colorizer', 'image colorizers', 'colorizes images', 'colorize images', 'colorizes image', 'colorize image', 'colorizes photos', 'colorize photos', 'colorizes the image', 'colorize the image', 'photo colorization', 'colorizes grayscale images', 'colorize grayscale images', 'colorizes black and white images', 'colorize black and white images', 'automatic image colorization', 'automated image colorization', 'image colorization software', 'image colorization app', 'image colorization program', 'colorizes your photos', 'adds color to images', 'add color to images', 'adds color to photos', 'add color to photos', 'colorizes black-and-white photos', 'colorize black-and-white photos', 'grayscale colorization', 'black and white colorization']
NOCOLORIZATION = ['does not support image colorization', 'do not support image colorization', "doesn't support image colorization", "don't support image colorization", 'no image colorization', 'without image colorization', 'never performs image colorization', 'does not perform image colorization', 'image colorization not supported', 'image colorization unsupported', 'no image colorization support', 'lacks image colorization', 'missing image colorization', 'image colorization disabled', 'no image colorization capability', 'without image colorization support', 'does not provide image colorization', 'no image colorization model', 'image colorization not available', 'does not use image colorization', 'no image colorizer', 'without image colorizer', 'does not support image colorizer', 'no photo colorizer']
GENERIC_NAMES = ['colorize_image', 'colorize_grayscale_image', 'colorize_photo', 'colorize_picture', 'colorize', 'add_color', 'apply_color', 'colorize_black_and_white', 'colorize_bw', 'grayscale_to_color', 'gray_to_color', 'colorize_image_file', 'image_colorization', 'photo_colorization', 'colorize_old_photo', 'restore_color', 'colorize_image_from_path', 'predict_color', 'colorize_grayscale', 'colorize_black_and_white_image', 'add_color_to_image', 'colorization_model', 'colorize_images', 'auto_colorize']
GET_IMAGE_COLORIZER_NAMES = ['get_image_colorizer']
GET_IMAGE_COLORIZER_SOURCES = ['deoldify', 'deoldify.visualize']
PIPELINE_CLASSES = ['ColorizationPipeline', 'ImageColorizationPipelineHF']
MODEL_CLASSES = ['DDColor', 'eccv16', 'siggraph17']
READ_NET_NAMES = ['readNetFromCaffe']

class OracleTests(unittest.TestCase):
    def test_colorization(self):
        self.assertEqual(phrases.COLORIZATION, COLORIZATION)
    def test_nocolorization(self):
        self.assertEqual(phrases.NOCOLORIZATION, NOCOLORIZATION)
    def test_generic_names(self):
        self.assertEqual(phrases.GENERIC_NAMES, GENERIC_NAMES)
    def test_get_image_colorizer_names(self):
        self.assertEqual(phrases.GET_IMAGE_COLORIZER_NAMES, GET_IMAGE_COLORIZER_NAMES)
    def test_get_image_colorizer_sources(self):
        self.assertEqual(phrases.GET_IMAGE_COLORIZER_SOURCES, GET_IMAGE_COLORIZER_SOURCES)
    def test_pipeline_classes(self):
        self.assertEqual(phrases.PIPELINE_CLASSES, PIPELINE_CLASSES)
    def test_model_classes(self):
        self.assertEqual(phrases.MODEL_CLASSES, MODEL_CLASSES)
    def test_read_net_names(self):
        self.assertEqual(phrases.READ_NET_NAMES, READ_NET_NAMES)

class MatchingTests(unittest.TestCase):
    def test_all_phrases(self):
        for phrase in COLORIZATION:
            with self.subTest(phrase=phrase):
                self.assertEqual(claims(phrase), ([phrase], []))
        for phrase in NOCOLORIZATION:
            with self.subTest(phrase=phrase):
                self.assertEqual(claims(phrase), ([], [phrase]))

    def test_longest_and_denials(self):
        self.assertEqual(claims('image colorization models'), (['image colorization models'], []))
        self.assertEqual(claims('image colorization model'), (['image colorization model'], []))
        self.assertEqual(claims('does not support image colorization')[0], [])

    def test_case_collision_fences_inline(self):
        self.assertEqual(claims('IMAGE COLORIZATION')[0], ['image colorization'])
        self.assertEqual(claims('colorize images with a CSS filter')[0], ['colorize images'])
        self.assertEqual(claims('```text\nimage colorization\n```'), ([], []))
        self.assertEqual(claims('`image colorization`')[0], ['image colorization'])
        self.assertEqual(claims('image--colorization'), ([], []))


class EvidenceTests(unittest.TestCase):
    def test_factory_routes(self):
        forms = [
            ('from deoldify import get_image_colorizer', 'get_image_colorizer'),
            ('from deoldify.visualize import get_image_colorizer', 'get_image_colorizer'),
            ('from deoldify.visualize import get_image_colorizer as g', 'g'),
            ('import deoldify', 'deoldify.get_image_colorizer'),
            ('import deoldify.visualize', 'deoldify.visualize.get_image_colorizer'),
            ('import deoldify.visualize as d', 'd.get_image_colorizer'),
            ('from deoldify import visualize', 'visualize.get_image_colorizer')]
        for imp, factory in forms:
            for method in ['get_transformed_image', 'plot_transformed_image', 'plot_transformed_image_from_url']:
                with self.subTest(imp=imp, method=method):
                    self.assertTrue(evidence(imp+'; c='+factory+'(); c.'+method+'(img)'))
                    self.assertTrue(evidence(imp+'; '+factory+'().'+method+'(img)'))

    def test_pipelines(self):
        for name in ['ColorizationPipeline', 'ImageColorizationPipelineHF']:
            for constructor in [name+'()', 'd.'+name+'()', 'P()']:
                prefix = 'from ddcolor import '+name+' as P; '
                self.assertTrue(evidence(prefix+'c='+constructor+'; c.process(img)'))
                self.assertTrue(evidence(prefix+constructor+'.process(img)'))

    def test_models(self):
        for name in ['DDColor', 'eccv16', 'siggraph17']:
            for constructor in [name+'()', 'colorizers.'+name+'()', 'M()']:
                prefix = 'from colorizers import '+name+' as M; '
                self.assertTrue(evidence(prefix+'c='+constructor+'; c(img)'))
                self.assertTrue(evidence(prefix+constructor+'(img)'))
                self.assertTrue(evidence(prefix+'c='+constructor+'.eval(); c(img)'))

    def test_networks(self):
        for prefix, call in [('', 'cv2.dnn.readNetFromCaffe'), ('from cv2.dnn import readNetFromCaffe; ', 'readNetFromCaffe'), ('from cv2.dnn import readNetFromCaffe as r; ', 'r')]:
            self.assertTrue(evidence(prefix+'n='+call+'("COLORIZATION.prototxt"); n.forward()'))
            self.assertTrue(evidence(prefix+call+'(path="colorization").forward()'))

    def test_generic_forms(self):
        for name in GENERIC_NAMES:
            for source in ['x.'+name+'(img)', 'from lib import '+name+'; '+name+'(img)', 'from lib import '+name+' as g; g(img)']:
                with self.subTest(source=source):
                    self.assertTrue(evidence(source))
            self.assertFalse(evidence(name+'(img)'))

    def test_unimported_network_and_wrong_instances(self):
        for code in [
            'n=readNetFromCaffe("colorization"); n.forward()',
            'c=ColorizationPipeline(); other.process(img)',
            'c=DDColor(); other(img)',
            'from deoldify import get_image_colorizer; c=get_image_colorizer(); other.get_transformed_image(img)',
            'n=cv2.dnn.readNetFromCaffe("colorization"); other.forward()']:
            with self.subTest(code=code):
                self.assertFalse(evidence(code))

    def test_rejections(self):
        cases = [
            'import deoldify, ddcolor, colorizers, cv2',
            'from deoldify import get_image_colorizer; c=get_image_colorizer()',
            'c=get_image_colorizer(); c.plot_transformed_image(img)',
            'import other; c=other.get_image_colorizer(); c.plot_transformed_image(img)',
            'from other import get_image_colorizer; c=get_image_colorizer(); c.plot_transformed_image(img)',
            'from deoldify import get_video_colorizer; c=get_video_colorizer(); c.plot_transformed_image(img)',
            'x.colorize_from_url(url)', 'c.plot_transformed_image(img)',
            'cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)', 'img.convert("L")',
            'x.denoise(img)', 'x.upscale(img)', 'x.inpaint(img)', 'x.generate(img)',
            'ImageEnhance.Color(img).enhance(2)', 'cv2.cvtColor(img, cv2.COLOR_BGR2HSV)',
            'x.segment(img)', 'x.detect(img)',
            '"colorization colorizer" # colorize_image(img)',
            'from lib import colorize_image; colorize_image',
            'subprocess.run(["colorization", "img"])',
            'n=cv2.dnn.readNetFromCaffe("other"); n.forward()',
            'n=cv2.dnn.readNetFromCaffe("colorization")',
            'def broken(']
        cases += [name+'()' for name in PIPELINE_CLASSES+MODEL_CLASSES]
        for code in cases:
            with self.subTest(code=code):
                self.assertFalse(evidence(code))

    def test_shadowing(self):
        routes = [
            ('get_image_colorizer', 'from deoldify import get_image_colorizer\nc=get_image_colorizer(); c.get_transformed_image(img)'),
            ('ColorizationPipeline', 'from lib import ColorizationPipeline\nc=ColorizationPipeline(); c.process(img)'),
            ('ImageColorizationPipelineHF', 'c=ImageColorizationPipelineHF(); c.process(img)'),
            ('DDColor', 'c=DDColor(); c(img)'), ('eccv16', 'c=colorizers.eccv16(); c(img)'),
            ('siggraph17', 'c=siggraph17(); c(img)'),
            ('readNetFromCaffe', 'from cv2.dnn import readNetFromCaffe\nc=readNetFromCaffe("colorization"); c.forward()'),
            ('colorize_image', 'from lib import colorize_image\ncolorize_image(img)')]
        for name, code in routes:
            for definition in ['def '+name+'(): pass\n', 'class '+name+': pass\n']:
                with self.subTest(name=name, definition=definition):
                    self.assertFalse(evidence(definition+code))


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def put(self, name, content):
        path = self.root/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')

    def cli(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            result = main(list(args))
        return result, out.getvalue(), err.getvalue()

    def test_bad_high_json(self):
        self.put('README.md', 'IMAGE COLORIZATION')
        code, out, _ = self.cli('audit', str(self.root), '--json')
        self.assertEqual(code, 2)
        data = json.loads(out)
        self.assertEqual(data['verdict'], 'FAIL')
        finding = data['findings'][0]
        self.assertEqual(finding['rule'], 'documented-image-colorization-claim-false')
        self.assertEqual(finding['severity'], 'HIGH')
        self.assertEqual(finding['verdict'], 'FAIL')
        self.assertTrue(finding['message'])

    def test_good(self):
        self.put('README.md', 'image colorization')
        self.put('run.py', 'x.colorize(img)')
        self.assertEqual(self.cli('audit', str(self.root))[0], 0)
        self.assertEqual(audit(self.root), [])

    def test_denial(self):
        self.put('README.md', 'no image colorization')
        self.assertEqual(audit(self.root), [])
        self.put('run.py', 'x.colorize(img)')
        findings = audit(self.root)
        self.assertEqual(findings[0]['rule'], 'documented-no-image-colorization-claim-false')
        self.assertEqual(findings[0]['severity'], 'HIGH')
        self.assertEqual(self.cli('audit', str(self.root))[0], 2)

    def test_test_only(self):
        self.put('tests/fixture.py', 'claim="image colorization"')
        self.assertEqual(audit(self.root)[0]['severity'], 'MEDIUM')
        self.assertEqual(self.cli('audit', str(self.root))[0], 0)
        self.assertEqual(self.cli('audit', str(self.root), '--fail-on', 'medium')[0], 2)

    def test_no_claim(self):
        self.put('README.md', 'Neutral text')
        self.assertEqual(self.cli('audit', str(self.root))[0], 0)

    def test_ignore_before_positional(self):
        self.put('docs/vendor/a.md', 'image colorization')
        self.assertEqual(self.cli('audit', str(self.root))[0], 2)
        self.assertEqual(self.cli('audit', '--ignore', 'docs/vendor/', str(self.root))[0], 0)
        self.assertEqual(self.cli('audit', str(self.root), '--ignore', 'docs/', '--ignore', 'other/')[0], 0)

    def test_split_modules(self):
        self.put('README.md', 'image colorization')
        self.put('a.py', 'from deoldify import get_image_colorizer\nc=get_image_colorizer()')
        self.put('b.py', 'c.get_transformed_image(img)')
        self.assertEqual(audit(self.root)[0]['severity'], 'HIGH')

    def test_scope_and_exclusions(self):
        self.put('other.md', 'image colorization')
        self.put('.venv/bad.py', 'x.colorize(img)')
        self.put('README.md', 'image colorization')
        self.assertEqual(audit(self.root)[0]['severity'], 'HIGH')
        self.put('README.md', 'neutral')
        self.assertEqual(audit(self.root), [])
        self.put('docs/nested/a.md', 'image colorization')
        self.assertEqual(audit(self.root)[0]['severity'], 'HIGH')

    def test_version(self):
        with self.assertRaises(SystemExit) as result:
            _, out, _ = self.cli('--version')
        self.assertEqual(result.exception.code, 0)
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit):
            main(['--version'])
        self.assertEqual(out.getvalue().strip(), '0.1.0')

    def test_usage_io_verbose(self):
        self.assertEqual(self.cli('audit', str(self.root/'missing'))[0], 1)
        self.assertEqual(self.cli('audit', '--fail-on', 'low')[0], 1)
        self.assertEqual(self.cli()[0], 1)
        self.put('README.md', 'neutral')
        code, _, err = self.cli('audit', str(self.root), '--verbose')
        self.assertEqual(code, 0)
        self.assertIn('Scope:', err)
        self.assertIn('README.md:', err)

    def test_readme_self_audit_only(self):
        readme = Path(__file__).resolve().parents[1]/'README.md'
        self.put('README.md', readme.read_text(encoding='utf-8'))
        self.assertEqual(claims(readme.read_text(encoding='utf-8')), ([], []))
        self.assertEqual(audit(self.root), [])
        self.assertEqual(self.cli('audit', str(self.root))[0], 0)

    def test_whole_project_medium(self):
        root = Path(__file__).resolve().parents[1]
        findings = audit(root)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0]['severity'], 'MEDIUM')
