#!/usr/bin/env python
# encoding: utf-8

import io, os, time
from tempfile import NamedTemporaryFile
import zbar
import zbar.misc
from skimage.io import imread as read_image
from PIL import Image
from wand.image import Image as WAND_Image

from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2.utils import PdfReadError


class File(object):

    def __init__(self, source, pages, qrcode):
        
        self.pages = pages
        self.qrcode = qrcode
        self.folder = "/mnt/"+self.qrcode.split("#")[1].replace('\\', '/').replace('[YYYY]', time.strftime("%Y")).replace('[MM]', time.strftime("%m")).replace('[DD]', time.strftime("%d")).replace('[hh]', time.strftime("%H")).replace('[mm]', time.strftime("%M")).replace('[ss]', time.strftime("%S"))
        if self.folder[-1] != "/":
            self.folder = self.folder + "/"
        self.file_name = self.qrcode.split("#")[2].replace('[YYYY]', time.strftime("%Y")).replace('[MM]', time.strftime("%m")).replace('[DD]', time.strftime("%d")).replace('[hh]', time.strftime("%H")).replace('[mm]', time.strftime("%M")).replace('[ss]', time.strftime("%S"))
        self.source = source

    def save(self, folder=None):
        
        tmpl = "[%s] from file '%s' copy page (%s) to %s"

        path = os.path.join(folder or self.folder, self.file_name)
        if path[-4:] == ".pdf":
            path = path[0:-4]
        
        try:
            if os.path.isfile(path+".pdf"):
                path = path + "_"
                for i in range(1,500):
                    if not os.path.isfile(path+str(i)+".pdf"):
                        path = path + str(i)
                        break
            path = path + ".pdf"
            with open(path, 'wb') as output: 
                wrt = PdfFileWriter()
                for num_page in self.pages:
                    wrt.addPage(self.source.reader.getPage(num_page))
                wrt.write(output)
                return tmpl % ('ok', self.source.source, self.pages, path)
        except Exception as ex:
            return tmpl % (ex, self.source.source, self.pages, path)


class Tool(object):
    def __init__(self, source=None):
        self.source = source
        self.__pages = {}
        self.__qrcodes = {}
        self.dpi = 150

        if not self.source:
            raise ValueError('Source is not set')
        try:
            self.reader = PdfFileReader(open(self.source, "rb"))
        except Exception as er:
            raise ValueError('Is not PDF [%s]' % self.source)
        else:

            head, tail = os.path.split(self.source)
            self.filename = '.'.join(tail.split('.')[:-1])
            self.__split_pages()
            
        return super(Tool, self).__init__()
    @property
    def pages_count(self):
        return self.reader.getNumPages()

    @property
    def pages(self):
        return self.__pages.values()

    @property
    def qrcodes(self):
        return sum(self.__qrcodes.values(), [])

    @property
    def files(self):
        __files = []
        pages = []
        qrcode = None
        for num in self.__pages.keys():
            if self.__pages[num]:
                continue
            barcodes = self.__qrcodes.get(num)
            if barcodes and barcodes[0][0] == "#":
                if num != 0:
                    __files.append(File(
                        self,
                        pages, 
                        qrcode
                    ))
                    pages = []
                qrcode = barcodes[0]
            else:
                if not qrcode:
                    raise ValueError('First page is not QRcode')
                pages.append(num)
                if num == max(list(self.__pages)):
                    __files.append(File(
                        self,
                        pages, 
                        qrcode
                    ))        
        return __files

    @staticmethod
    def code(file_path=None, barcode_type='QRCODE'):
        image = read_image(file_path)
        
        if len(image.shape) == 3:
            image = zbar.misc.rgb2gray(image)
        
        barcodes = []

        scanner = zbar.Scanner()
        results = scanner.scan(image)
        for barcode in results:
            barcodes.append(barcode.data.decode(u'utf-8'))    
        
            
        return barcodes
            
    def __split_pages(self):
        for count_index, num in enumerate(range(self.pages_count), 1):
            self.__pages[num] = False
            page = self.reader.getPage(num)
            with NamedTemporaryFile(delete=False) as tmp:
                
                wrt = PdfFileWriter()
                wrt.addPage(page)
                wrt.write(tmp)
                tmp.close()
                with NamedTemporaryFile(delete=False) as out:
                    with WAND_Image(filename=tmp.name, resolution=150) as img:
                        img.format = 'jpg'
                        img.save(file=out)
                    
                    out.close()
                    with Image.open(out.name) as img:
                        min, max = img.convert("L").getextrema()
                        print("valeurs min: "+str(min)+" max: "+str(max))
                        if max - min < 15:
                            self.__pages[num] = True
                        else:
                            total_px = 0
                            px_valides = 0
                            for nb_px, rgb_val in img.convert("L").getcolors():
                                total_px = total_px + nb_px
                                if rgb_val < max - 15:
                                    px_valides = px_valides + nb_px
                            
                            print("Px_valides : "+str(px_valides*100000/total_px)+" / 100000")
                            print(img.convert("L").getcolors())
                            if px_valides*100000/total_px < 5:
                                self.__pages[num] = True
                    print(out.name)
                    self.__qrcodes[num] = Tool.code(out.name)

                    os.unlink(out.name)

                os.unlink(tmp.name)

