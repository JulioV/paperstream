# -*- mode: python -*-

block_cipher = None


a = Analysis(['__main__.py'],
             pathex=['./'],
             binaries=[],
             datas=[(r'./static', 'static'),
                    (r'./input', 'input'),
                    (r'./output', 'output'),
                    (r'./log_configuration.ini','.')],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)

pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          exclude_binaries=True,
          name='PaperStream',
          debug=False,
          strip=False,
          upx=False,
          console=True )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=False,
               name='paperstream')
