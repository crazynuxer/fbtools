// Framebuffer I/O, because pure python is waaaay too slow
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <errno.h>
#include <linux/fb.h>

struct fbinfo
{
    uint32_t height,    // height in pixels
             width,     // width in pixels
             bpp,       // bytes per pixel: 2, 3, or 4. If 2 bytes, then colorspace is 565.
             red,       // red shift
             green,     // green shift
             blue;      // blue shift
    void   * mmap;      // pointer to frame buffer memory
};

int fbopen(struct fbinfo *fb, char *device)
{
    int fd=open(device, O_RDWR);
    if (fd < 0) return 1;

    struct fb_var_screeninfo vsi;
    if (ioctl(fd, FBIOGET_VSCREENINFO, &vsi) < 0)
    {
        close(fd);
        return 2;
    }

    if (vsi.bits_per_pixel == 32 && vsi.red.length == 8 && vsi.green.length == 8 && vsi.blue.length == 8)
    {
        // ARGB
        fb->bpp=4;
    }
    else if (vsi.bits_per_pixel == 24 && vsi.red.length == 8 && vsi.green.length == 8 && vsi.blue.length == 8)
    {
        // RGB
        fb->bpp=3;
    }
    else if (vsi.bits_per_pixel == 16 && vsi.red.length == 5 && vsi.green.length == 6 && vsi.blue.length == 5)
    {
        // 565
        fb->bpp=2;
    } else
    {
        close(fd);
        return 3;
    }

    fb->height = vsi.yres_virtual;
    fb->width = vsi.xres_virtual;
    fb->red = vsi.red.offset;
    fb->green = vsi.green.offset;
    fb->blue = vsi.blue.offset;

    fb->mmap=mmap(NULL, vsi.xres_virtual * vsi.yres_virtual * fb->bpp, PROT_READ|PROT_WRITE, MAP_SHARED, fd, 0);
    close(fd);

    if (fb->mmap == MAP_FAILED)
    {
        return 4;
    }

    return 0;
}

// Unpack pixels from framebuffer pixel offset to raw rgb data and return 0.
// Return 1 if pixels+offset is out of range. *rgfb size must be pixels*3 bytes
int fbunpack(struct fbinfo *fb, uint32_t pixels, uint32_t offset, uint8_t *rgb)
{
    if (offset+pixels > fb->height*fb->width) return 1;

    switch(fb->bpp)
    {
        case 2:
        {
            uint16_t *p = fb->mmap+(offset*2);
            while (pixels--)
            {
                uint16_t n = *p++;
                *rgb++ = (n >> fb->red) << 3;
                *rgb++ = (n >> fb->green) << 2;
                *rgb++ = (n >> fb->blue) << 3;
            }
            break;
        }
        case 3:
        {
            uint8_t *p = fb->mmap+(offset*3);
            while (pixels--)
            {
                uint32_t n = (*p++ << 0) + (*p++ << 8) + (*p++ << 16); // little-endian
                *rgb++ = n >> fb->red;
                *rgb++ = n >> fb->green;
                *rgb++ = n >> fb->blue;

            }
        }
        case 4:
        {
            uint32_t *p = fb->mmap+(offset*4);
            while (pixels--)
            {
                uint32_t n = *p++;
                *rgb++ = n >> fb->red;
                *rgb++ = n >> fb->green;
                *rgb++ = n >> fb->blue;
            }
            break;
        }
    }
    return 0;
}

// Pack pixels of raw rgb data to framebuffer specified pixel offset and return
// 0. Error ERANGE if pixels+offset out of range. *rgb must be pixels*3 bytes
// long.
int fbpack(struct fbinfo *fb, uint32_t pixels, uint32_t offset, uint8_t *rgb)
{
    if (offset+pixels > fb->height*fb->width) return 1;

    switch(fb->bpp)
    {
        case 2:
        {
            uint16_t *p = fb->mmap+(offset*2);
            while (pixels--)
            {
                *p++ = ((rgb[0]>>3) << fb->red) | ((rgb[1]>>2) << fb->green) | ((rgb[2]>>3) << fb->blue);
                rgb += 3;
            }
            break;
        }
        case 3:
        {
            uint8_t *p = fb->mmap+(offset*3);
            while (pixels--)
            {
                uint32_t n = (rgb[0] << fb->red) | (rgb[1] << fb->green) | (rgb[2] << fb->blue);
                *p++ = n; *p++ = n>>8; *p++ = n >> 16; // little-endian
                rgb += 3;
            }
            break;
        }
        case 4:
        {
            uint32_t *p = fb->mmap+(offset*4);

            while (pixels--)
            {
                *p++ = (rgb[0] << fb->red) | (rgb[1] << fb->green) | (rgb[2] << fb->blue) | 0xff000000;
                rgb += 3;
            }
            break;
        }
    }
    return 0;
}
