import math
import cv2
import numpy as np
import Preprocess

ADAPTIVE_THRESH_BLOCK_SIZE = 19
ADAPTIVE_THRESH_WEIGHT = 9

Min_char_area = 0.015
Max_char_area = 0.06

Min_char = 0.01
Max_char = 0.09

Min_ratio_char = 0.25
Max_ratio_char = 0.7

max_size_plate = 18000
min_size_plate = 5000

RESIZED_IMAGE_WIDTH = 20
RESIZED_IMAGE_HEIGHT = 30

tongframe = 0
biensotimthay = 0

# Load KNN model
npaClassifications = np.loadtxt("classifications.txt", np.float32)
npaFlattenedImages = np.loadtxt("flattened_images.txt", np.float32)
npaClassifications = npaClassifications.reshape((npaClassifications.size, 1))
kNearest = cv2.ml.KNearest_create()
kNearest.train(npaFlattenedImages, cv2.ml.ROW_SAMPLE, npaClassifications)

# Sử dụng camera để đọc hình ảnh
cap = cv2.VideoCapture(0)  # 0 cho camera mặc định, nếu có nhiều camera bạn có thể thay đổi thành 1, 2...

while (cap.isOpened()):
    ret, img = cap.read()
    if not ret:  # Nếu không lấy được hình ảnh
        print("Không thể đọc hình ảnh từ camera")
        break

    tongframe += 1

    # Tiền xử lý hình ảnh
    imgGrayscaleplate, imgThreshplate = Preprocess.preprocess(img)
    canny_image = cv2.Canny(imgThreshplate, 250, 255)
    kernel = np.ones((3, 3), np.uint8)
    dilated_image = cv2.dilate(canny_image, kernel, iterations=1)

    # Tìm biển số xe
    contours, hierarchy = cv2.findContours(dilated_image, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)[:10]
    screenCnt = []

    for c in contours:
        peri = cv2.arcLength(c, True)
        approx = cv2.approxPolyDP(c, 0.06 * peri, True)
        [x, y, w, h] = cv2.boundingRect(approx.copy())
        ratio = w / h
        if (len(approx) == 4) and (0.8 <= ratio <= 1.5 or 4.5 <= ratio <= 6.5):
            screenCnt.append(approx)

    detected = 1 if screenCnt else 0  # Cách kiểm tra có tìm thấy biển số

    if detected == 1:
        n = 1
        for screenCnt in screenCnt:
            ################## Tìm góc của biển số ###############
            (x1, y1) = screenCnt[0, 0]
            (x2, y2) = screenCnt[1, 0]
            (x3, y3) = screenCnt[2, 0]
            (x4, y4) = screenCnt[3, 0]
            array = [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]
            sorted_array = sorted(array, key=lambda x: x[1], reverse=True)
            (x1, y1) = sorted_array[0]
            (x2, y2) = sorted_array[1]

            doi = abs(y1 - y2)
            ke = abs(x1 - x2)
            angle = math.atan(doi / ke) * (180.0 / math.pi)

            # Mask phần khác ngoài biển số
            mask = np.zeros(imgGrayscaleplate.shape, np.uint8)
            new_image = cv2.drawContours(mask, [screenCnt], 0, 255, -1)

            # Cắt biển số
            (x, y) = np.where(mask == 255)
            (topx, topy) = (np.min(x), np.min(y))
            (bottomx, bottomy) = (np.max(x), np.max(y))

            roi = img[topx:bottomx + 1, topy:bottomy + 1]
            imgThresh = imgThreshplate[topx:bottomx + 1, topy:bottomy + 1]

            ptPlateCenter = (bottomx - topx) / 2, (bottomy - topy) / 2

            if x1 < x2:
                rotationMatrix = cv2.getRotationMatrix2D(ptPlateCenter, -angle, 1.0)
            else:
                rotationMatrix = cv2.getRotationMatrix2D(ptPlateCenter, angle, 1.0)

            roi = cv2.warpAffine(roi, rotationMatrix, (bottomy - topy, bottomx - topx))
            imgThresh = cv2.warpAffine(imgThresh, rotationMatrix, (bottomy - topy, bottomx - topy))

            roi = cv2.resize(roi, (0, 0), fx=3, fy=3)
            imgThresh = cv2.resize(imgThresh, (0, 0), fx=3, fy=3)

            # Tiền xử lý biển số
            kerel3 = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            thre_mor = cv2.morphologyEx(imgThresh, cv2.MORPH_DILATE, kerel3)
            cont, hier = cv2.findContours(thre_mor, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            # Phân đoạn ký tự
            char_x_ind = {}
            char_x = []
            height, width, _ = roi.shape
            roiarea = height * width

            for ind, cnt in enumerate(cont):
                area = cv2.contourArea(cnt)
                (x, y, w, h) = cv2.boundingRect(cont[ind])
                ratiochar = w / h
                if (Min_char * roiarea < area < Max_char * roiarea) and (0.25 < ratiochar < 0.7):
                    if x in char_x:  # Sử dụng để dù cho trùng x vẫn vẽ được
                        x = x + 1
                    char_x.append(x)
                    char_x_ind[x] = ind

            # Nhận diện ký tự
            if len(char_x) in range(7, 10):
                cv2.drawContours(img, [screenCnt], -1, (0, 255, 0), 3)

                char_x = sorted(char_x)
                strFinalString = ""
                first_line = ""
                second_line = ""

                for i in char_x:
                    (x, y, w, h) = cv2.boundingRect(cont[char_x_ind[i]])
                    cv2.rectangle(roi, (x, y), (x + w, y + h), (0, 255, 0), 2)

                    imgROI = thre_mor[y:y + h, x:x + w]  # Cắt ký tự

                    imgROIResized = cv2.resize(imgROI,
                                               (RESIZED_IMAGE_WIDTH, RESIZED_IMAGE_HEIGHT))  # thay đổi kích thước
                    npaROIResized = imgROIResized.reshape(
                        (1, RESIZED_IMAGE_WIDTH * RESIZED_IMAGE_HEIGHT))  # Đưa hình ảnh về mảng 1 chiều
                    npaROIResized = np.float32(npaROIResized)  # chuyển mảng về dạng float
                    _, npaResults, neigh_resp, dists = kNearest.findNearest(npaROIResized, k=3)
                    strCurrentChar = str(chr(int(npaResults[0][0])))  # ASCII của ký tự
                    cv2.putText(roi, strCurrentChar, (x, y + 50), cv2.FONT_HERSHEY_DUPLEX, 2, (0, 255, 255), 3)

                    if (y < height / 3):
                        first_line += strCurrentChar
                    else:
                        second_line += strCurrentChar

                strFinalString = first_line + second_line
                print("\nBiển số " + str(n) + " là: " + strFinalString)  # In biển số ra console
                cv2.putText(img, strFinalString, (topy, topx), cv2.FONT_HERSHEY_DUPLEX, 1, (0, 255, 255), 1)
                n += 1
                biensotimthay += 1

                # Hiển thị hình ảnh biển số đã nhận diện
                cv2.imshow("Biển số đã nhận diện", cv2.cvtColor(roi, cv2.COLOR_BGR2RGB))

    imgcopy = cv2.resize(img, None, fx=0.5, fy=0.5)
    cv2.imshow('Kết quả nhận diện', imgcopy)

    key = cv2.waitKey(1)
    if key == ord('q'):  # Nhấn 'q' để thoát
        break

cap.release()
cv2.destroyAllWindows()
